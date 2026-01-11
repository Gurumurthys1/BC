import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import io
import requests

# Define the model architecture
class Model(nn.Module):
    def __init__(self):
        super(Model, self).__init__()
        self.fc1 = nn.Linear(4, 10) # 4 input features
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(10, 1) # 1 output
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.sigmoid(self.fc2(x))
        return x

def train(dataset_url):
    """
    Standard training entry point for OBLIVION workers.
    Args:
        dataset_url (str): URL or path to the dataset.
    Returns:
        tuple: (list of gradients, float loss_value)
    """
    print(f"Loading dataset from: {dataset_url}")
    
    # 1. Load Data
    # Handle local file or URL
    if dataset_url.startswith('http'):
        s = requests.get(dataset_url).content
        df = pd.read_csv(io.StringIO(s.decode('utf-8')))
    else:
        # For local testing
        df = pd.read_csv(dataset_url)
    
    # Prepare Tensors
    X = torch.tensor(df.iloc[:, :4].values, dtype=torch.float32)
    y = torch.tensor(df.iloc[:, 4].values, dtype=torch.float32).unsqueeze(1)
    
    # 2. Initialize Model
    model = Model()
    criterion = nn.BCELoss()
    optimizer = optim.SGD(model.parameters(), lr=0.1)
    
    # 3. Training Loop (Simple 1-step for demo)
    optimizer.zero_grad()
    outputs = model(X)
    loss = criterion(outputs, y)
    loss.backward()
    
    # 4. Extract Gradients
    gradients = [p.grad for p in model.parameters()]
    loss_value = loss.item()
    
    return gradients, loss_value
