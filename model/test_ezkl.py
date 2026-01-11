import ezkl
import os

import asyncio

async def main():
    base_path = os.path.abspath("model")
    model_path = os.path.join(base_path, "network.onnx")
    settings_path = os.path.join(base_path, "settings_test.json")
    compiled_model_path = os.path.join(base_path, "network_test.ezkl")
    pk_path = os.path.join(base_path, "pk_test.key")
    vk_path = os.path.join(base_path, "vk_test.key")

    print("Generating settings...")
    run_args = ezkl.PyRunArgs()
    run_args.input_scale = 10
    run_args.param_scale = 10
    ezkl.gen_settings(model_path, settings_path, py_run_args=run_args)

    print("Compiling model...")
    ezkl.compile_circuit(model_path, compiled_model_path, settings_path)

    print("Getting SRS...")
    ezkl.get_srs(settings_path)

    print("Generating witness...")
    witness_path = os.path.join("model", "witness_test.json")
    data_path = os.path.join("model", "input.json")
    ezkl.gen_witness(data_path, compiled_model_path, witness_path)

    print("Mocking...")
    res = ezkl.mock(
        witness_path,
        compiled_model_path,
        settings_path,
    )
    print(f"Mock result: {res}")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
