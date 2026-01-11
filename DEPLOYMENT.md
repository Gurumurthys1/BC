# Deployment Guide: OBLIVION Distributed AI

This guide covers how to host the frontend publicly and run distributed worker nodes on multiple machines.

## 1. Public Frontend Hosting (Vercel)

The easiest way to host the Next.js frontend is via Vercel.

### Prerequisites
- A GitHub account.
- The project pushed to a GitHub repository.

### Steps
1.  **Push to GitHub**:
    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    git branch -M main
    git remote add origin <YOUR_REPO_URL>
    git push -u origin main
    ```

2.  **Deploy on Vercel**:
    - Go to [vercel.com](https://vercel.com) and log in.
    - Click "Add New..." -> "Project".
    - Import your GitHub repository.
    - **Environment Variables**: Add the variables from your `.env` file (Supabase keys, RPC URL).
    - Click "Deploy".

3.  **Public URL**: Vercel will give you a public URL (e.g., `https://oblivion-ai.vercel.app`).

---

## 2. Setting up Distributed Workers

You can run worker nodes on any machine (your laptop, a server, a friend's computer) to join the compute mesh.

### Prerequisites (On each worker machine)
- Python 3.8+ installed.
- Internet connection.

### Steps
1.  **Copy the Worker Client**:
    - You only need the `node-client` directory.
    - Copy the `node-client` folder to the target machine.

2.  **Install Dependencies**:
    ```bash
    cd node-client
    pip install torch numpy supabase web3 python-dotenv requests
    # On Windows, you might need: pip install torch --index-url https://download.pytorch.org/whl/cu118
    ```

3.  **Configure Environment**:
    - Create a `.env` file in the `node-client` folder with the SAME Supabase keys used by the frontend:
    ```env
    SUPABASE_URL=https://your-project.supabase.co
    SUPABASE_KEY=your-anon-key
    RPC_URL=https://polygon-amoy-bor-rpc.publicnode.com
    ```

4.  **Run the Worker**:
    ```bash
    python sharded_worker.py
    ```

### Behavior
- **First Run**: The worker will generate a unique ID and save it to `node_id.txt`.
- **Registration**: It will automatically register itself in the `nodes` table.
- **Heartbeat**: It sends a heartbeat every 30s so the dashboard knows it's online.
- **Job Processing**: When a training job is posted on the frontend, ANY active worker can pick it up.

---

## 3. Database Configuration (Critical)

For the public registration to work, you MUST run the provided SQL script in your Supabase SQL Editor.

1.  Go to your Supabase Dashboard -> SQL Editor.
2.  Open `database/update_nodes_policy.sql` from this project.
3.  Copy and paste the content into the SQL Editor.
4.  Run the script.

This allows public workers to insert their presence into the `nodes` table.
