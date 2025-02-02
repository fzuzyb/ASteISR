import torch
from torch import nn as nn
from torch.nn import functional as F
import itertools
from torchvision.models.vgg import vgg16
from torchvision.models import alexnet
from collections import OrderedDict

from basicsr.archs.vgg_arch import VGGFeatureExtractor
from basicsr.utils.registry import LOSS_REGISTRY
from .loss_util import weighted_loss

_reduction_modes = ['none', 'mean', 'sum']


@weighted_loss
def l1_loss(pred, target):
    return F.l1_loss(pred, target, reduction='none')


@weighted_loss
def mse_loss(pred, target):
    return F.mse_loss(pred, target, reduction='none')


@weighted_loss
def charbonnier_loss(pred, target, eps=1e-12):
    return torch.sqrt((pred - target)**2 + eps)


@LOSS_REGISTRY.register()
class L1Loss(nn.Module):
    """L1 (mean absolute error, MAE) loss.

    Args:
        loss_weight (float): Loss weight for L1 loss. Default: 1.0.
        reduction (str): Specifies the reduction to apply to the output.
            Supported choices are 'none' | 'mean' | 'sum'. Default: 'mean'.
    """

    def __init__(self, loss_weight=1.0, reduction='mean'):
        super(L1Loss, self).__init__()
        if reduction not in ['none', 'mean', 'sum']:
            raise ValueError(f'Unsupported reduction mode: {reduction}. Supported ones are: {_reduction_modes}')

        self.loss_weight = loss_weight
        self.reduction = reduction

    def forward(self, pred, target, weight=None, **kwargs):
        """
        Args:
            pred (Tensor): of shape (N, C, H, W). Predicted tensor.
            target (Tensor): of shape (N, C, H, W). Ground truth tensor.
            weight (Tensor, optional): of shape (N, C, H, W). Element-wise weights. Default: None.
        """
        return self.loss_weight * l1_loss(pred, target, weight, reduction=self.reduction)


@LOSS_REGISTRY.register()
class MSELoss(nn.Module):
    """MSE (L2) loss.

    Args:
        loss_weight (float): Loss weight for MSE loss. Default: 1.0.
        reduction (str): Specifies the reduction to apply to the output.
            Supported choices are 'none' | 'mean' | 'sum'. Default: 'mean'.
    """

    def __init__(self, loss_weight=1.0, reduction='mean'):
        super(MSELoss, self).__init__()
        if reduction not in ['none', 'mean', 'sum']:
            raise ValueError(f'Unsupported reduction mode: {reduction}. Supported ones are: {_reduction_modes}')

        self.loss_weight = loss_weight
        self.reduction = reduction

    def forward(self, pred, target, weight=None, **kwargs):
        """
        Args:
            pred (Tensor): of shape (N, C, H, W). Predicted tensor.
            target (Tensor): of shape (N, C, H, W). Ground truth tensor.
            weight (Tensor, optional): of shape (N, C, H, W). Element-wise weights. Default: None.
        """
        return self.loss_weight * mse_loss(pred, target, weight, reduction=self.reduction)


@LOSS_REGISTRY.register()
class CharbonnierLoss(nn.Module):
    """Charbonnier loss (one variant of Robust L1Loss, a differentiable
    variant of L1Loss).

    Described in "Deep Laplacian Pyramid Networks for Fast and Accurate
        Super-Resolution".

    Args:
        loss_weight (float): Loss weight for L1 loss. Default: 1.0.
        reduction (str): Specifies the reduction to apply to the output.
            Supported choices are 'none' | 'mean' | 'sum'. Default: 'mean'.
        eps (float): A value used to control the curvature near zero. Default: 1e-12.
    """

    def __init__(self, loss_weight=1.0, reduction='mean', eps=1e-12):
        super(CharbonnierLoss, self).__init__()
        if reduction not in ['none', 'mean', 'sum']:
            raise ValueError(f'Unsupported reduction mode: {reduction}. Supported ones are: {_reduction_modes}')

        self.loss_weight = loss_weight
        self.reduction = reduction
        self.eps = eps

    def forward(self, pred, target, weight=None, **kwargs):
        """
        Args:
            pred (Tensor): of shape (N, C, H, W). Predicted tensor.
            target (Tensor): of shape (N, C, H, W). Ground truth tensor.
            weight (Tensor, optional): of shape (N, C, H, W). Element-wise weights. Default: None.
        """
        return self.loss_weight * charbonnier_loss(pred, target, weight, eps=self.eps, reduction=self.reduction)


@LOSS_REGISTRY.register()
class WeightedTVLoss(L1Loss):
    """Weighted TV loss.

    Args:
        loss_weight (float): Loss weight. Default: 1.0.
    """

    def __init__(self, loss_weight=1.0, reduction='mean'):
        if reduction not in ['mean', 'sum']:
            raise ValueError(f'Unsupported reduction mode: {reduction}. Supported ones are: mean | sum')
        super(WeightedTVLoss, self).__init__(loss_weight=loss_weight, reduction=reduction)

    def forward(self, pred, weight=None):
        if weight is None:
            y_weight = None
            x_weight = None
        else:
            y_weight = weight[:, :, :-1, :]
            x_weight = weight[:, :, :, :-1]

        y_diff = super().forward(pred[:, :, :-1, :], pred[:, :, 1:, :], weight=y_weight)
        x_diff = super().forward(pred[:, :, :, :-1], pred[:, :, :, 1:], weight=x_weight)

        loss = x_diff + y_diff

        return loss


@LOSS_REGISTRY.register()
class PerceptualLoss(nn.Module):
    """Perceptual loss with commonly used style loss.

    Args:
        layer_weights (dict): The weight for each layer of vgg feature.
            Here is an example: {'conv5_4': 1.}, which means the conv5_4
            feature layer (before relu5_4) will be extracted with weight
            1.0 in calculating losses.
        vgg_type (str): The type of vgg network used as feature extractor.
            Default: 'vgg19'.
        use_input_norm (bool):  If True, normalize the input image in vgg.
            Default: True.
        range_norm (bool): If True, norm images with range [-1, 1] to [0, 1].
            Default: False.
        perceptual_weight (float): If `perceptual_weight > 0`, the perceptual
            loss will be calculated and the loss will multiplied by the
            weight. Default: 1.0.
        style_weight (float): If `style_weight > 0`, the style loss will be
            calculated and the loss will multiplied by the weight.
            Default: 0.
        criterion (str): Criterion used for perceptual loss. Default: 'l1'.
    """

    def __init__(self,
                 layer_weights,
                 vgg_type='vgg19',
                 use_input_norm=True,
                 range_norm=False,
                 perceptual_weight=1.0,
                 style_weight=0.,
                 criterion='l1'):
        super(PerceptualLoss, self).__init__()
        self.perceptual_weight = perceptual_weight
        self.style_weight = style_weight
        self.layer_weights = layer_weights
        self.vgg = VGGFeatureExtractor(
            layer_name_list=list(layer_weights.keys()),
            vgg_type=vgg_type,
            use_input_norm=use_input_norm,
            range_norm=range_norm)

        self.criterion_type = criterion
        if self.criterion_type == 'l1':
            self.criterion = torch.nn.L1Loss()
        elif self.criterion_type == 'l2':
            self.criterion = torch.nn.L2loss()
        elif self.criterion_type == 'fro':
            self.criterion = None
        else:
            raise NotImplementedError(f'{criterion} criterion has not been supported.')

    def forward(self, x, gt):
        """Forward function.

        Args:
            x (Tensor): Input tensor with shape (n, c, h, w).
            gt (Tensor): Ground-truth tensor with shape (n, c, h, w).

        Returns:
            Tensor: Forward results.
        """
        # extract vgg features
        x_features = self.vgg(x)
        gt_features = self.vgg(gt.detach())

        # calculate perceptual loss
        if self.perceptual_weight > 0:
            percep_loss = 0
            for k in x_features.keys():
                if self.criterion_type == 'fro':
                    percep_loss += torch.norm(x_features[k] - gt_features[k], p='fro') * self.layer_weights[k]
                else:
                    percep_loss += self.criterion(x_features[k], gt_features[k]) * self.layer_weights[k]
            percep_loss *= self.perceptual_weight
        else:
            percep_loss = None

        # calculate style loss
        if self.style_weight > 0:
            style_loss = 0
            for k in x_features.keys():
                if self.criterion_type == 'fro':
                    style_loss += torch.norm(
                        self._gram_mat(x_features[k]) - self._gram_mat(gt_features[k]), p='fro') * self.layer_weights[k]
                else:
                    style_loss += self.criterion(self._gram_mat(x_features[k]), self._gram_mat(
                        gt_features[k])) * self.layer_weights[k]
            style_loss *= self.style_weight
        else:
            style_loss = None

        return percep_loss, style_loss

    def _gram_mat(self, x):
        """Calculate Gram matrix.

        Args:
            x (torch.Tensor): Tensor with shape of (n, c, h, w).

        Returns:
            torch.Tensor: Gram matrix.
        """
        n, c, h, w = x.size()
        features = x.view(n, c, w * h)
        features_t = features.transpose(1, 2)
        gram = features.bmm(features_t) / (c * h * w)
        return gram


# LPIPS
class LPIPSBaseNet(nn.Module):
    def __init__(self):
        super(LPIPSBaseNet, self).__init__()

        # register buffer
        self.register_buffer(
            'mean', torch.Tensor([-.030, -.088, -.188])[None, :, None, None])
        self.register_buffer(
            'std', torch.Tensor([.458, .448, .450])[None, :, None, None])

    def set_requires_grad(self, state):
        for param in itertools.chain(self.parameters(), self.buffers()):
            param.requires_grad = state

    def z_score(self, x):
        return (x - self.mean) / self.std

    def normalize_activation(self, x, eps=1e-10):
        norm_factor = torch.sqrt(torch.sum(x ** 2, dim=1, keepdim=True))
        return x / (norm_factor + eps)

    def forward(self, x):
        x = self.z_score(x)
        output = []
        for i, (_, layer) in enumerate(self.layers._modules.items(), 1):
            x = layer(x)
            if i in self.target_layers:
                output.append(self.normalize_activation(x))
            if len(output) == len(self.target_layers):
                break
        return output


class LPIPSAlexNet(LPIPSBaseNet):
    def __init__(self):
        super(LPIPSAlexNet, self).__init__()

        self.layers = alexnet(True).features
        self.target_layers = [2, 5, 8, 10, 12]
        self.n_channels_list = [64, 192, 384, 256, 256]

        self.set_requires_grad(False)


class LPIPSVGG16(LPIPSBaseNet):
    def __init__(self):
        super(LPIPSVGG16, self).__init__()

        self.layers = vgg16(True).features
        self.target_layers = [4, 9, 16, 23, 30]
        self.n_channels_list = [64, 128, 256, 512, 512]

        self.set_requires_grad(False)


@LOSS_REGISTRY.register()
class LPIPSLoss(nn.Module):
    r"""Creates a criterion that measures
    Learned Perceptual Image Patch Similarity (LPIPS).

    Arguments:
        net_type (str): the network type to compare the features:
                        'alex' | 'squeeze' | 'vgg'. Default: 'alex'.
        alpha (List):
    """

    def __init__(self, net_type='vgg', alpha=None, perceptual_weight=1.0,use_rangenorm=False):
        super(LPIPSLoss, self).__init__()

        # pretrained network
        if alpha is None:
            self.alpha = [1, 1, 1, 1, 1]
        else:
            self.alpha = alpha
        self.net = self.get_network(net_type)

        self.use_rangenorm = use_rangenorm
        # linear layers
        self.lin = self.LPIPSLinLayers(self.net.n_channels_list)
        self.lin.load_state_dict(self.get_state_dict(net_type), strict=True)

        self.perceptual_weight = perceptual_weight

        # # the mean is for image with range [0, 1]
        # self.register_buffer('mean', torch.Tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        # # the std is for image with range [0, 1]
        # self.register_buffer('std', torch.Tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))
    def LPIPSLinLayers(self, n_channels_list):

        modulelist = nn.ModuleList(
            [nn.Sequential(nn.Identity(), nn.Conv2d(nc, 1, 1, 1, 0, bias=False)) for nc in n_channels_list])

        for param in modulelist.parameters():
            param.requires_grad = False
        return modulelist

    def get_state_dict(self, net_type):
        # build state dict
        old_state_dict = torch.load("./experiments/pretrained_models/lpips_{}.pth".format(net_type), map_location='cpu')

        # rename keys
        new_state_dict = OrderedDict()
        for key, val in old_state_dict.items():
            new_key = key
            new_key = new_key.replace('lin', '')
            new_key = new_key.replace('model.', '')
            new_state_dict[new_key] = val

        return new_state_dict

    def get_network(self, net_type):
        if net_type == 'alex':
            return LPIPSAlexNet()
        elif net_type == 'vgg':
            return LPIPSVGG16()
        else:
            raise NotImplementedError('choose net_type from [alex, vgg].')

    def forward(self, x, gt):
        '''
        Args:
            x (Tensor): Input tensor with shape (n, c, h, w).
            gt (Tensor): Ground-truth tensor with shape (n, c, h, w).

        Returns:
            Tensor: Forward results.
        :return:
        '''
        if self.use_rangenorm:
            x = (x - 0.5) * 2
            gt = (gt - 0.5) * 2

        if self.perceptual_weight>0:
            feat_x, feat_y = self.net(x), self.net(gt.detach())
            diff = [(fx - fy) ** 2 for fx, fy in zip(feat_x, feat_y)]
            res = [l(d).mean((2, 3), True) * a for a, d, l in zip(self.alpha, diff, self.lin)]

            return self.perceptual_weight * torch.sum(torch.cat(res, 0)),None
        else:
            return None,None
# LPIPS

# stereoBMLoss
@LOSS_REGISTRY.register()
class StereoBMLoss(nn.Module):
    def __init__(self, numDisparities=128, blockSize=21):
        super(StereoBM, self).__init__()
        self.numDisparities = numDisparities
        self.blockSize = blockSize

    def forward(self, x,gt):
        '''
              Args:
                  x (Tensor): Input tensor with shape (n, c, h, w).
                  gt (Tensor): Ground-truth tensor with shape (n, c, h, w).

              Returns:
                  Tensor: Forward results.
              :return:
              '''
        # 图像预处理
        left_gt, right_gt = gt[:,:3,:,:],gt[:,3:,:,:]
        left_pred, right_pred = x[:,:3,:,:],x[:,3:,:,:]
        # 计算视差
        disparity_gt = self.calculate_disparity(left_gt, right_gt)
        disparity_pred = self.calculate_disparity(left_pred, right_pred)

        # 计算loss
        loss = F.l1_loss(disparity_pred, disparity_gt, reduction='mean')

        return loss

    def calculate_disparity(self, img_left, img_right):
        img_left = F.normalize(img_left, p=2, dim=1)
        img_right = F.normalize(img_right, p=2, dim=1)

        # 创建输出视差图
        disparity = torch.zeros(img_left.shape[0], 1, img_left.shape[2], img_left.shape[3], device=img_left.device)

        # 设置搜索窗口大小
        search_range = self.numDisparities * self.blockSize

        # 获取左图的每个块
        left_blocks = F.unfold(img_left, kernel_size=self.blockSize, stride=1, padding=self.blockSize//2)

        # 在右图中搜索匹配块
        for k in range(max(self.blockSize//2 - self.numDisparities, -img_left.shape[3] + self.blockSize//2), min(search_range - img_left.shape[3] - self.blockSize//2, img_right.shape[3] - self.blockSize//2 - img_left.shape[3] + self.blockSize//2)):
            right_blocks = F.unfold(img_right[:, :, :, k:k+img_left.shape[3]], kernel_size=self.blockSize, stride=1, padding=self.blockSize//2)
            match = F.l1_loss(left_blocks, right_blocks, reduction='mean')
            match = match.reshape(img_left.shape[0], -1, img_left.shape[2], img_left.shape[3])
            mask = torch.logical_and((k <= disparity) , (disparity < k + self.numDisparities)).float()
            disparity = torch.where(mask.byte(), disparity, k + match.argmin(dim=1).unsqueeze(1))

        # 后处理
        disparity = disparity.squeeze(1)

        return disparity