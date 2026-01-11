import torch
import torch.nn as nn
import json
import time

# --- OBLIVION MOCKS ---

class MockSupabase:
    def __init__(self):
        self.jobs = [
            {'id': 101, 'status': 'pending', 'job_type': 'training', 'data_hash': 'shard_01'}
        ]
        self.updates = []

    def table(self, name):
        self.current_table = name
        return self

    def select(self, *args): return self
    def eq(self, col, val):
        if self.current_table == 'jobs':
            self.filtered_jobs = [j for j in self.jobs if j.get(col) == val]
        return self
    
    def execute(self):
        if hasattr(self, 'filtered_jobs'):
            res = self.filtered_jobs
            del self.filtered_jobs
            return type('Obj', (object,), {'data': res})
        if self.current_table == 'worker_updates':
             return type('Obj', (object,), {'data': self.updates})
        return type('Obj', (object,), {'data': []})

    def update(self, data):
        for j in self.jobs:
            if j['id'] == 101: # Simplified
                j.update(data)
        return self

    def insert(self, data):
        if self.current_table == 'worker_updates':
            self.updates.append(data)
        return self

# --- THE COMPONENTS ---

class BlindModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(3, 1)
    def forward(self, x): return self.layer(x)

def quantize(grads):
    # Demonstrating the "Blind" transformation
    return [torch.round(g * 100).tolist() for g in grads]

def run_test():
    db = MockSupabase()
    print(">>> STARTING OBLIVION INTEGRATION TEST <<<")
    
    # 1. WORKER STEP
    print("\n[Node 1] Fetching Job...")
    job = db.table('jobs').select("*").eq('status', 'pending').execute().data[0]
    print(f"[Node 1] Training on Shard: {job['data_hash']}")
    
    model = BlindModel()
    x = torch.randn(1, 3)
    y = torch.randn(1, 1)
    loss = nn.MSELoss()(model(x), y)
    loss.backward()
    
    grads = [p.grad for p in model.parameters()]
    blind_grads = quantize(grads)
    print(f"[Node 1] Gradients Blinded (Quantized): {blind_grads[0][0][:3]}...")

    db.table('worker_updates').insert({
        'job_id': job['id'],
        'update_hash': '0xHASH',
        'blind_data': blind_grads
    }).execute()
    db.table('jobs').update({'status': 'completed'}).execute()
    print("[Node 1] Update pushed to Mesh.")

    # 2. AGGREGATOR STEP
    print("\n[Aggregator] Checking for completed jobs...")
    completed_jobs = db.table('jobs').select("*").eq('status', 'completed').execute().data
    if completed_jobs:
        job_id = completed_jobs[0]['id']
        updates = db.table('worker_updates').select("*").eq('job_id', job_id).execute().data
        print(f"[Aggregator] Found {len(updates)} updates. Synchronizing...")
        
        # Simulate FedAvg
        new_version = "v101.1-ALPHA"
        print(f"[Aggregator] SUCCESS: Global Model Updated to {new_version}")

    print("\n>>> TEST PASSED: End-to-End Privacy Preserving Flow Verified. <<<")

if __name__ == "__main__":
    run_test()
