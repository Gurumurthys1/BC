import torch
import torch.nn as nn
import torch.optim as optim
import onnx
import json
import os

# Define a simple model for ZK proof generation
class SimpleModel(nn.Module):
    """
    A simple neural network model compatible with ezkl ZK proof generation.
    Architecture: Linear -> ReLU -> Linear
    """
    def __init__(self, input_dim=3, hidden_dim=10, output_dim=2):
        super(SimpleModel, self).__init__()
        self.layer1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.layer2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = self.layer1(x)
        x = self.relu(x)
        x = self.layer2(x)
        return x

def main():
    print("=== OBLIVION: Model Training & ONNX Export ===")
    
    # 1. Initialize the model
    model = SimpleModel(input_dim=3, hidden_dim=10, output_dim=2)
    
    # 2. Optional: Train the model with sample data
    print("Training model with sample data...")
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()
    
    # Generate synthetic training data
    for epoch in range(100):
        x_train = torch.randn(32, 3)
        y_train = torch.randn(32, 2)
        
        optimizer.zero_grad()
        outputs = model(x_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 25 == 0:
            print(f"  Epoch [{epoch+1}/100], Loss: {loss.item():.4f}")
    
    # Set model to evaluation mode
    model.eval()
    print("Training complete.")

    # Create dummy input for export
    x = torch.randn(1, 3, requires_grad=False)

    # 3. Export to ONNX
    onnx_path = os.path.join("model", "network.onnx")
    os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
    
    print(f"Exporting model to ONNX format: {onnx_path}")
    torch.onnx.export(
        model,
        x,
        onnx_path,
        export_params=True,
        opset_version=12,
        do_constant_folding=False,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={
            'input': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )
    print(f"Model exported to {onnx_path}")

    # 4. Create a sample input file for ZK proof generation
    input_data = dict(input_data=x.reshape([-1]).tolist())
    input_path = os.path.join("model", "input.json")
    with open(input_path, 'w') as f:
        json.dump(input_data, f, indent=2)
    print(f"Input data saved to {input_path}")
    
    # 5. Save PyTorch model weights as well
    weights_path = os.path.join("model", "model_weights.pt")
    torch.save(model.state_dict(), weights_path)
    print(f"Model weights saved to {weights_path}")
    
    print("\n=== Export Complete ===")
    print("Next steps:")
    print("  1. Run compile_circuit.py to generate ZK circuit")
    print("  2. Deploy the generated Verifier.sol contract")

if __name__ == "__main__":
    main()
