import cv2
import glob
import sys 
import os
import os.path as osp
import  xml.dom.minidom
from torch import nn
import torch
sys.path.insert(0, '../../vmaf/wrapper')
sys.path.insert(0, '../../')
from src.utils import frames_to_video, y4m2yuv
from IPython import embed
import numpy as np
import time
import argparse
from multiprocessing import Process
import shutil

result_dir = 'submit_results'
if not osp.exists(result_dir):
    os.mkdir(result_dir)
    
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test_LR_dir', type=str, default = '../../dataset/submit/youku_00200_00249_l')
    parser.add_argument('--model_path', type = str, default = None)
    parser.add_argument('--ngpu', type = int, default = 1)
    parser.add_argument('--nframes', type = int, default = 7)
    args = parser.parse_args()
    return args    

def construct_model(model_path, device, nframes):
    from model import G
    model = G(nframes)
    ckpt = torch.load(model_path)
    new_ckpt  = {}
    for key in ckpt:
        if key.startswith('module'):
            new_key  = key[7:]
        else:
            new_key = key
        new_ckpt[new_key] = ckpt[key]
    model = model.to(device)
    model.load_state_dict(new_ckpt)
    model.eval()
    return model

def test_net(gpu_id, model_path, video_list, timeline, nframes):
    os.environ["CUDA_VISIBLE_DEVICES"] = "{}".format(gpu_id)
    device = torch.device('cuda:0')
    model = construct_model(model_path, device, nframes)

    for video_name in video_list:
        if osp.isfile(osp.join(test_LR_dir, video_name)):
            continue
        print('testing  ', video_name) 
        imglist = glob.glob(osp.join(test_LR_dir, video_name, '*.bmp'))
        imglist.sort(key=lambda x:(x.split('/')[-1][:-4]))
        result_img_dir = osp.join(result_dir, video_name)
        if not osp.exists(result_img_dir):
            os.mkdir(result_img_dir)
        for i in range(nframes//2):
            img = cv2.imread(imglist[i]) / 255
            img_name = imglist[i].split('/')[-1]
            img = cv2.resize(img, dsize=None, fx=4, fy=4, interpolation = cv2.INTER_CUBIC)
            cv2.imwrite(osp.join(result_img_dir, img_name), img*255)
            
            img = cv2.imread(imglist[-i]) / 255
            img_name = imglist[-i].split('/')[-1]
            img = cv2.resize(img, dsize=None, fx=4, fy=4, interpolation = cv2.INTER_CUBIC)
            cv2.imwrite(osp.join(result_img_dir, img_name), img*255)
            
        for i in range(len(imglist) - nframes):
            img = []
            for j in range(nframes):
                img.append(cv2.imread(imglist[i + j]) / 255)
            img  = np.stack(img, 0).transpose(3, 0, 1, 2)[None]
            img_name = imglist[i + nframes//2].split('/')[-1]
            
            h = img.shape[3]
            w = img.shape[4]
            HR_img = np.zeros(shape=(1,3, h*4, w*4))
            start_row = [_*100 for _ in range(h//100)]
            start_row.append(h - 100)
            start_col = [_*100 for _ in range(w//100)]
            start_col.append(w - 100)
            
            for row in start_row:
                for col in start_col:
                    patch = torch.as_tensor(img[:,:,:,row:row+100, col:col+100]).float().cuda()
                    HR_img[:,:,row*4:row*4+100*4, col*4:col*4 + 100*4] = model(patch).cpu().detach().numpy() * 255
                           
            HR_img  = np.squeeze(HR_img).transpose(1,2,0)
            HR_img = np.clip(HR_img, 0, 255)
            cv2.imwrite(osp.join(result_img_dir, img_name), HR_img)

        video_path = frames_to_video(result_img_dir)
        new_video_path  = video_path.split('/')
        new_video_path[-1] = video_name.replace('_l','_h_Res.y4m')
        os.rename(video_path,osp.join(*new_video_path))

def sample_video():
    results_y4m = glob.glob(osp.join(result_dir, 'Youku_*_Res.y4m'))
    results_y4m.sort(key = lambda x: int(x.split('_')[2]))
    print(results_y4m)
    sample_start = int(0.1 * len(results_y4m))
    for i in range(sample_start, len(results_y4m),1):
        name = results_y4m[i].split('.')[0]
        new_name = name.replace('_Res','_Sub25_Res')
        print(new_name)
        cmd = "ffmpeg -i {}.y4m -vf select='not(mod(n\,25))' -vsync 0  -y {}.y4m".format(name, new_name)
        os.system(cmd)
#         shutil.rmtree(results_y4m[i])

    
if __name__=='__main__':
    args = parse_args()
    test_LR_dir = args.test_LR_dir
#     test_HR_dir = args.test_HR_dir
    
    video_list  = []
    for _ in os.listdir(test_LR_dir):
        if osp.isdir(osp.join(test_LR_dir, _ )):
            video_list.append(_)
            
    sub_video_list = []
    stride = len(video_list)//args.ngpu
    for i in range(args.ngpu):
        if i <args.ngpu - 1:
            tmp = video_list[stride*i:stride*(i+1)]
        else:
            tmp = video_list[stride*i:]
        sub_video_list.append(tmp)
                            
    workers = []
    timeline = int(time.time() * 1e6)
    
    for gpu_id in range(args.ngpu):
        workers.append(Process(target=test_net, args=(gpu_id, args.model_path, sub_video_list[gpu_id], timeline, args.nframes)))
    
    for i, w in enumerate(workers):
        print("Woker {} started".format(i))
        w.start()
    for i, w in enumerate(workers):
        w.join()
        print("Woker {} finished".format(i))
        
    sample_video()