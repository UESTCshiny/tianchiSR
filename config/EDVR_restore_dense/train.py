import torch.nn as nn
import torch
from torchvision import transforms
import torchvision
from torchvision.utils import make_grid
import time
import copy
import os

def train_model(model, optimizer,scheduler, dataloader, summery_writer, device,args):
    
    Iter = 0
    for epoch in range(args.num_epochs):
        print('Epoch {}/{}'.format(epoch, args.num_epochs - 1))
        print('-' * 10)
        
        model.train()
        scheduler.step()
        
        for index, (img, label) in enumerate(dataloader,0):
            Iter += 1
            img = img.float().to(device)
            label = label.float().to(device)
            optimizer.zero_grad()
            
            gen_imgs = model(img)
            
            losses = []
            total_loss = 0.0
            for gen_img in gen_imgs:
                loss = nn.L1Loss(reduction='mean')(label, gen_img)
                losses.append(loss)
                total_loss += loss
            loss_  = nn.MSELoss(reduction='mean')(label, gen_imgs[-1])
            total_loss.backward()
            optimizer.step()
            
            if Iter % args.display_fre == 0:
                lr = scheduler.get_lr()[-1]
                print("Loss:{}, lr:{}".format(loss_.item(), lr))
                summery_writer.add_scalar('scaler/loss', losses[-1].item(), Iter)
                summery_writer.add_scalar('scaler/lr', lr, Iter)
                summery_writer.add_image('images/LR', torchvision.utils.make_grid(img[:,args.nframes//2]), Iter)
                summery_writer.add_image('images/gen', torchvision.utils.make_grid(gen_imgs[-1], nrow=2), Iter)
                summery_writer.add_image('images/HR', torchvision.utils.make_grid(label, nrow=2), Iter)
                
        
        # Each epoch has a training and validation phase
        torch.save(model.state_dict(),os.path.join(args.save_dir,'model-{}.pkl'.format(epoch)))


    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
