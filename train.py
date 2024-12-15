import shutil
import time
from PIL import Image
import torch.nn as nn
from torch.autograd import Variable
from nets.crackformer_SeMask_ssconv_splat import crackformer
from utils.utils import *
from utils.Validator import *
from utils.Crackloader import *
from git.repo import Repo
from git.repo.fun import is_git_dir
import cv2

os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
os.environ["CUDA_VISIBLE_DEVICES"] = '0,1'

# device = torch.device("cpu")

def trainer(net, total_epoch, lr_init, batch_size,train_img_dir, valid_img_dir, valid_lab_dir,
            valid_result_dir, valid_log_dir, best_model_dir, image_format, lable_format, pretrain_dir=None):

    # 输入训练图片,制作成dataset,dataset其实就是一个List 结构如同：[[img1,gt1],[img2,gt2],[img3,gt3]]

    img_data = Crackloader(txt_path=train_img_dir, normalize=False)

    #  加载数据 用pytorch给我们设计的加载器，可以自动打乱
    img_batch = data.DataLoader(img_data, batch_size=batch_size, shuffle=True, num_workers=2)

    # 这是根据机器有几块GPU进行选择
    print('Using', torch.cuda.device_count(), 'GPUs.')
    if torch.cuda.device_count() > 1:
        crack = nn.DataParallel(net).cuda()
    else:
        crack = net.cuda()  # 如果没有多块GPU需要用这种方法

    # 可以加载训练好的模型
    if pretrain_dir is not None:
        crack = torch.load(pretrain_dir).cuda()

    # 生成验证器
    validator = Validator(valid_img_dir, valid_lab_dir,
                          valid_result_dir, valid_log_dir, best_model_dir, crack,  image_format, lable_format)
    # 训练的核心部分

    for epoch in range(1, total_epoch):

        losses = Averagvalue()

        crack.train()  # 选择训练状态

        count = 0 # 记录在当前epoch下第几个item，即当前epoch下第几次更新参数

        # 关于学习率更新的办法
        new_lr = updateLR(lr_init, epoch, total_epoch)

        print('Learning Rate: {:.9f}'.format(new_lr))

        # optimizer
        lr = new_lr
        optimizer = torch.optim.Adam(crack.parameters(), lr=lr)

        # with torch.no_grad():
        for (images, labels) in img_batch:
            count += 1
            loss = 0
            
            # 前向传播部分
            images = Variable(images).cuda()
            labels = Variable (labels.float()).cuda()

            output = crack.forward(images)
            for out in output:
                loss += 0.5 * crack.calculate_loss(out, labels)
            loss += 1.1 * crack.calculate_loss(output[-1], labels)
            #计算损失部分
            optimizer.zero_grad()
            
            loss.backward()
            optimizer.step()

            #打印输出损失，lr等
            losses.update(loss.item(), images.size(0))
            lr = optimizer.param_groups[0]['lr']
            if count%10==0:
                info = 'Epoch: [{0}/{1}][{2}/{3}] '.format(epoch, total_epoch, count, len(img_batch)) + \
                    'Loss {loss.val:f} (avg:{loss.avg:f} lr {lr:.10f}) '.format(
                        loss=losses, lr=lr)
                with open(valid_log_dir + "/loss.txt", 'a', encoding='utf-8') as fout:
                    fout.write(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + '：' + info + '\n')
                print(info)
            # validator.validate(i)
        if epoch % 2 == 0:
            print("test.txt valid")
            validator.validate(epoch)
            local_path = ''
            git_local_path = os.path.join(local_path, '.git')
            if is_git_dir(git_local_path):
                print('开始上传结果')
                repo = Repo(local_path) # 已经存在git仓库
                # repo.git.remote('add', 'origin', 'https://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@github.com/WillCAI2020/kaggle-result.git')
                repo.git.add(valid_result_dir)
                repo.git.add(valid_log_dir)
                repo.git.add(best_model_dir)
                repo.git.commit('-m', 'epoch {}'.format(epoch))
                repo.git.push()
                print('上传结束')

if __name__ == '__main__':

    datasetName="CrackLS315"
    dataName= "train"
    netName = "crackformer"
    # 
    image_format = "jpg"
    lable_format = "bmp"

    # total_epoch = 500
    # lr_init = 0.001
    total_epoch = 500
    lr_init = 0.001
    batch_size = 1

    net = crackformer()

    train_img_dir = "/datasets/"+ datasetName +"/" + dataName +".txt"
    valid_img_dir = "/datasets/"+datasetName+"/valid/200a/"
    valid_lab_dir = "/datasets/"+datasetName+"/valid/200b/"
    valid_result_dir = "/datasets/"+datasetName+ "/valid/200res/"
    valid_log_dir = "/log/" + netName 
    best_model_dir = "/model/" + datasetName +"/"
    # pretrain_dir=""
    trainer(net, total_epoch, lr_init, batch_size, train_img_dir, valid_img_dir, valid_lab_dir,
            valid_result_dir, valid_log_dir, best_model_dir,  image_format, lable_format) #, pretrain_dir=pretrain_dir

    # # 保存方式2，模型参数（官方推荐）
    # torch.save(net.state_dict(), "net_method1.pth")

    print("训练结束")

