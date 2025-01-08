# A Universal Parameter-Efficient Fine-Tuning Approach for Stereo Image Super-Resolution
# Original Title: ASteISR: Adapting Single Image Super-resolution Pre-trained Model for Efficient Stereo Image Super-resolution

[Arixv Paper](https://arxiv.org/pdf/2407.03598v1)
### News
**2025.01.07** The Baseline, including the pretrained models and train/test configs, are available now.

### Installation
This implementation based on [BasicSR](https://github.com/xinntao/BasicSR) which is a open source toolbox for image/video restoration tasks.
    
    conda create -n torch2 python==3.9
    pip install -r  requirements.txt  -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
    cd  ASteISR
    python setup.py develop
            
### Base hardware Requirements
- : 2 A40 GPUs

## 1. Quick Test 
#### 1.1 Download the pretrained model to the dir of 'experiments/pretrained_models'.
#####
   *pretrained model can be download at [百度网盘](https://pan.baidu.com/s/1ZyqeUoUEnfpFxQcQGP0zUw?pwd=axs4),
       
#### 1.2 Modify the dataroot_lq: in  'options/test/ASSR'
        test_ASteISR_HATNet-L_2x.yml
        test_ASteISR_HATNet-L_4x.yml

#### 1.3 Run the test scripts 
        sh test.sh
#### 1.4 The final results are in 'results'

If ASteISR is helpful, please help to ⭐ the repo.

If you find this project useful for your research, please consider citing our paper:
### BibTex
    @inproceedings{zhou2023stereo,
      title={Stereo Cross Global Learnable Attention Module for Stereo Image Super-Resolution},
      author={Zhou, Yuanbo and Xue, Yuyang and Deng, Wei and Nie, Ruofeng and Zhang, Jiajun and Pu, Jiaqi and Gao, Qinquan and Lan, Junlin and Tong, Tong},
      booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
      pages={1416--1425},
      year={2023}
    }

    @article{zhou2024asteisr,
        title={ASteISR: Adapting Single Image Super-resolution Pre-trained Model for Efficient Stereo Image Super-resolution},
        author={Zhou, Yuanbo and Xue, Yuyang and Deng, Wei and Zhang, Xinlin and Gao, Qinquan and Tong, Tong},
        journal={arXiv preprint arXiv:2407.03598},
        year={2024}
   }

    

### Contact

If you have any questions, please contact webbozhou@gmail.com 
 

    
    
    
    
        
