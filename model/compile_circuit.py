import ezkl
import os
import json
import asyncio

async def main():
    model_path = os.path.join("model", "network.onnx")
    settings_path = os.path.join("model", "settings.json")
    data_path = os.path.join("model", "input.json")
    compiled_model_path = os.path.join("model", "network.ezkl")
    pk_path = os.path.join("model", "pk.key")
    vk_path = os.path.join("model", "vk.key")
    witness_path = os.path.join("model", "witness.json")
    proof_path = os.path.join("model", "proof.json")

    # 0. Check if model exists
    if not os.path.exists(model_path):
        print(f"Error: {model_path} not found. Run train.py first.")
        return

    # 1. Generate Settings
    print("Generating settings...")
    # Using lower scales to avoid decomposition errors
    run_args = ezkl.PyRunArgs()
    run_args.input_scale = 8
    run_args.param_scale = 8
    run_args.decomp_legs = 4
    ezkl.gen_settings(model_path, settings_path, py_run_args=run_args)
    
    # 2. Calibrate Settings (optional but recommended)
    # print("Calibrating settings...")
    # ezkl.calibrate_settings(data_path, model_path, settings_path, "resources")

    # 3. Compile the model
    print("Compiling model...")
    ezkl.compile_circuit(model_path, compiled_model_path, settings_path)

    # 4. Get SRS (Structured Reference String)
    print("Getting SRS...")
    # This downloads a public SRS. In production, you might want to pin this.
    ezkl.get_srs(settings_path)

    # 5. Setup (Generate Keys)
    print("Setting up keys (PK and VK)...")
    ezkl.setup(
        compiled_model_path,
        vk_path,
        pk_path,
    )

    # 6. Generate Witness
    print("Generating witness...")
    ezkl.gen_witness(data_path, compiled_model_path, witness_path)

    # 7. Generate Proof
    print("Generating proof...")
    ezkl.prove(
        witness_path,
        compiled_model_path,
        pk_path,
        proof_path,
        "single", # proof_type
    )

    print("Proof generated successfully!")

    # 8. Verify Proof locally
    print("Verifying proof locally...")
    res = ezkl.verify(
        proof_path,
        settings_path,
        vk_path,
    )
    print(f"Verification result: {res}")

    # 9. Create Solidity Verifier
    print("Creating Solidity Verifier...")
    solidity_verifier_path = os.path.join("contracts", "src", "Verifier.sol")
    os.makedirs(os.path.dirname(solidity_verifier_path), exist_ok=True)
    
    # Need to read the circuit settings to get the SRS path if needed, 
    # but verify_circuit returns a boolean. 
    # create_evm_verifier returns True on success? 
    
    # ezkl.create_evm_verifier needs paths
    ezkl.create_evm_verifier(
        vk_path,
        settings_path,
        solidity_verifier_path,
    )
    print(f"Verifier contract created at {solidity_verifier_path}")

if __name__ == "__main__":
    asyncio.run(main())
