import sys
sys.path.append("..")
from champs.datasets import ChampsDataset, ChampsDatasetMultiTarget
from champs.models import Net
from torch_geometric.data import DataLoader
import torch.nn.functional as F
import torch


dim = 64

dataset = ChampsDatasetMultiTarget("./data/")
# Normalize targets to mean = 0 and std = 1.
mean = dataset.data.y.mean(dim=0)
std = dataset.data.y.std(dim=0)
print(mean, std)
dataset.data.y = (dataset.data.y - mean) / std

# Split datasets.
val_dataset = dataset[::5]
train_dataset = dataset[1::5]
train_loader = DataLoader(
    train_dataset, batch_size=64,
    num_workers=2,
    pin_memory=True,
)
val_loader = DataLoader(
    val_dataset, batch_size=64,
    num_workers=2,
    pin_memory=True,
)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = Net(dataset.num_features, dim).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='min', factor=0.7, patience=5, min_lr=0.00001)


def log_mae(predict, truth):
    predict = predict.view(-1)
    truth = truth.view(-1)

    score = torch.abs(predict-truth)
    score = score.mean()
    score = torch.log(score)
    return score


def mae(predict, truth):
    predict = predict.view(-1)
    truth = truth.view(-1)

    score = torch.abs(predict-truth)
    score = score.sum()
    return score


def weighted_log_mae(predict, truth, weights):
    predict = predict.view(-1)
    truth = truth.view(-1)

    score = torch.abs(predict-truth)
    score = torch.log(score) * weights
    score = score.sum()
    return score


def train(epoch):
    model.train()
    loss_all = 0

    for data in train_loader:
        data = data.to(device)
        optimizer.zero_grad()
        loss = mae(model(data), data.y)
        loss.backward()
        loss_all += loss.item()
        optimizer.step()
    return loss_all / len(train_loader.dataset)


def test(loader):
    model.eval()
    error = 0

    for data in loader:
        data = data.to(device)
        error += mae(model(data), data.y).item()
    return error / len(loader.dataset)


best_val_error = None
for epoch in range(1, 101):
    lr = scheduler.optimizer.param_groups[0]['lr']
    loss = train(epoch)
    val_error = test(val_loader)
    scheduler.step(val_error)
    print('Epoch: {:03d}, LR: {:7f}, Loss: {:.7f}, Validation MAE: {:.7f}'.format(epoch, lr, loss, val_error))

    # if 0:
    if epoch % 10 == 0:
        torch.save(model.state_dict(), './checkpoint/multiscale.{:04d}_model.pth'.format(epoch))
        torch.save({
            'optimizer': optimizer.state_dict(),
            'epoch': epoch,
            'val_loss': val_error,
        }, './checkpoint/{:04d}_optimizer.pth'.format(epoch))
