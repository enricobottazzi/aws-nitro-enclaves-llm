"""
Module to run an LLM inside of a nitro enclave
"""
import json
import socket
from transformers import AutoTokenizer, AutoModelForCausalLM


def main(): #pylint: disable=R0914
    """
    Main function to load model, create socket connections, and process prompts
    """
    model_name = "/app/bloom"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model = AutoModelForCausalLM.from_pretrained(model_name)

    sock_connect = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    cid = socket.VMADDR_CID_ANY
    port = 5000
    sock_connect.bind((cid, port))
    sock_connect.listen()
    print(f"Started server on port {port} and cid {cid}")

    while True:
        connection, addr = sock_connect.accept() #pylint: disable=w0612
        payload = connection.recv(4096)
        result_dict = {}
        
        try:
            request_data = json.loads(payload.decode())
            prompt = request_data.get('prompt', '')
            print(f"Received prompt: {prompt}")

            # Encode the input text with padding enabled
            inputs = tokenizer(prompt, return_tensors="pt", padding=True, truncation=True)

            # Ensure that the input tensor has the proper shape for batch generation
            input_ids = inputs.input_ids.repeat(1, 1)

            # Generate text with padding
            outputs = model.generate(
                input_ids,
                max_length=20,
                do_sample=True,
                top_k=5,
                num_return_sequences=1,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"Result: {generated_text}")

            result_dict["Results"] = generated_text
        except Exception as e:
            result_dict["error"] = str(e)
            print(f"Error processing request: {e}")

        connection.send(str.encode(json.dumps(result_dict)))
        connection.close()


if __name__ == '__main__':
    main()
