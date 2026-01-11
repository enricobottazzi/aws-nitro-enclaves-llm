"""
Simple client that runs on EC2 instance to send plaintext prompts to the enclave
and log the responses (no encryption/decryption)
"""
import json
import socket
import subprocess
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_client.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_cid():
    """
    Determine CID of Current Enclave
    """
    try:
        with subprocess.Popen(
            ["/bin/nitro-cli", "describe-enclaves"],
            stdout=subprocess.PIPE
        ) as proc:
            output = json.loads(proc.communicate()[0].decode())
            if not output:
                raise ValueError("No enclaves found. Make sure the enclave is running.")
            enclave_cid = output[0]["EnclaveCID"]
            return enclave_cid
    except Exception as e:
        logger.error(f"Failed to get enclave CID: {e}")
        raise


def send_prompt(prompt, cid=None, port=5000):
    """
    Send a plaintext prompt to the enclave and return the response
    
    Args:
        prompt: The text prompt to send to the LLM
        cid: The enclave CID (if None, will be retrieved automatically)
        port: The vsock port to connect to (default: 5000)
    
    Returns:
        The response from the LLM as a string
    """
    if cid is None:
        cid = get_cid()
    
    logger.info(f"Connecting to enclave CID: {cid}, port: {port}")
    logger.info(f"Sending prompt: {prompt}")
    
    # Create a vsock socket object
    sock_connect = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    
    try:
        # Connect to the server
        sock_connect.connect((cid, port))
        
        # Prepare plaintext request
        request = {
            "prompt": prompt,
            "mode": "plaintext"
        }
        
        # Send the prompt to the server running in enclave
        request_json = json.dumps(request)
        sock_connect.send(str.encode(request_json))
        
        # Receive data from the server
        received_data = sock_connect.recv(4096).decode()
        
        # Parse response
        response = json.loads(received_data)
        
        # Log the response
        if "error" in response:
            logger.error(f"Error from enclave: {response['error']}")
            return None
        elif "Results" in response:
            logger.info(f"Response from LLM: {response['Results']}")
            return response["Results"]
        else:
            logger.warning(f"Unexpected response format: {response}")
            return response
            
    except socket.error as e:
        logger.error(f"Socket error: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse response: {e}")
        logger.error(f"Raw response: {received_data}")
        raise
    finally:
        sock_connect.close()


def main():
    """
    Main function to send prompts interactively or from command line
    """
    if len(sys.argv) > 1:
        # If prompt provided as command line argument
        prompt = " ".join(sys.argv[1:])
        logger.info("Using prompt from command line arguments")
    else:
        # Interactive mode
        print("Simple Enclave Client - Plaintext Mode")
        print("Enter prompts to send to the LLM in the enclave (type 'exit' to quit)")
        prompt = input("Enter your prompt: ").strip()
        
        if not prompt or prompt.lower() == 'exit':
            logger.info("Exiting...")
            return
    
    try:
        response = send_prompt(prompt)
        if response:
            print(f"\nLLM Response: {response}\n")
        else:
            print("\nNo response received from enclave\n")
    except Exception as e:
        logger.error(f"Failed to send prompt: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
