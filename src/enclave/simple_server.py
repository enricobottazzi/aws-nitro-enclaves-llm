"""
Simple server that runs inside a nitro enclave to process LLM requests
without encryption/decryption. This is useful for testing and development.
"""
import json
import socket
from transformers import AutoTokenizer, AutoModelForCausalLM


def process_llm_request(plaintext, tokenizer, model):
    """
    Process a plaintext prompt through the LLM and return the generated text
    
    Args:
        plaintext: The input prompt text
        tokenizer: The tokenizer for the model
        model: The LLM model
    
    Returns:
        Generated text from the LLM
    """
    # Encode the input text with padding enabled
    inputs = tokenizer(plaintext, return_tensors="pt", padding=True, truncation=True)

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
    return generated_text


def handle_request(request_data, tokenizer, model):
    """
    Handle a plaintext request and return the response
    
    Args:
        request_data: Dictionary containing the request data
        tokenizer: The tokenizer for the model
        model: The LLM model
    
    Returns:
        Dictionary containing the response or error
    """
    result_dict = {}
    
    if "prompt" not in request_data:
        result_dict["error"] = "Missing 'prompt' field in request"
        return result_dict
    
    prompt = request_data["prompt"]
    print(f"Received plaintext prompt: {prompt}")
    
    try:
        generated_text = process_llm_request(prompt, tokenizer, model)
        result_dict["Results"] = generated_text
        result_dict["status"] = "success"
    except Exception as e:
        result_dict["error"] = f"LLM processing failed: {str(e)}"
        result_dict["status"] = "error"
        print(f"Error processing LLM request: {e}")
    
    return result_dict


def main():
    """
    Main function to load model, create socket connections, and process requests
    """
    print("Loading LLM model...")
    model_name = "/app/bloom"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model = AutoModelForCausalLM.from_pretrained(model_name)
    print("Model loaded successfully!")

    # Create vsock socket
    sock_connect = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    cid = socket.VMADDR_CID_ANY
    port = 5000
    sock_connect.bind((cid, port))
    sock_connect.listen()
    print(f"Simple server started on port {port} and cid {cid}")
    print("Ready to accept plaintext requests...")

    while True:
        try:
            connection, addr = sock_connect.accept()
            print(f"Connection accepted from {addr}")
            
            # Receive request
            payload = connection.recv(4096)
            if not payload:
                connection.close()
                continue
                
            request_data = json.loads(payload.decode())
            print(f"Received request with keys: {list(request_data.keys())}")
            
            # Process request
            result_dict = handle_request(request_data, tokenizer, model)
            
            # Send response
            response_json = json.dumps(result_dict)
            connection.send(str.encode(response_json))
            print(f"Response sent: {result_dict.get('status', 'unknown')}")
            
            connection.close()
            
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            error_response = {"error": f"Invalid JSON: {str(e)}", "status": "error"}
            connection.send(str.encode(json.dumps(error_response)))
            connection.close()
        except Exception as e:
            print(f"Unexpected error: {e}")
            error_response = {"error": f"Server error: {str(e)}", "status": "error"}
            try:
                connection.send(str.encode(json.dumps(error_response)))
                connection.close()
            except:
                pass


if __name__ == '__main__':
    main()
