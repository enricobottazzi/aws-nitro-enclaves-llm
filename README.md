# AWS Nitro Enclave Large Language Models

This project contains an example implementation of how Nitro Enclaves can help protect LLM model deployments, specifically those that use personally identifiable information (PII) or protected health information (PHI). This post is for educational purposes only and should not be used in production environments without additional controls.

## Architecture

![](./docs/architecture.png)

User data, including PII, PHI, and questions, remains encrypted throughout the request-response process when the application is hosted within an enclave. The steps carried out during the inference are as follows:

1. The chatbot app generates temporary AWS credentials and asks the user to input a question. The question, which may contain PII or PHI, is then encrypted via AWS KMS. The encrypted user input is combined with the temporary credentials to create the encrypted request.

2. The encrypted data is sent to an HTTP server hosted by Flask as a POST request. Before accepting sensitive data, this endpoint should be configured for HTTPs.

3. The client app receives the POST request and forwards it through a secure local channel (for example, vsock) to the server app running inside Nitro Enclaves.

4. The Nitro Enclaves server app uses the temporary credentials to decrypt the request, queries the LLM, and generates the response. The model-specific settings are stored within the enclaves and are protected with cryptographic attestation.

5. The server app uses the same temporary credentials to encrypt the response.

6. The encrypted response is returned back to the chatbot app through the client app as a response from the POST request.

7. The chatbot app decrypts the response using their KMS key and displays the plaintext to the user.

## Environment Setup

# Create an AWS KMS CMK (NO)
1.	Log in to the AWS Management Console and select the AWS region where you’d like to deploy these resources.
2.	Navigate to the AWS KMS by searching for “KMS” in the AWS Management Console search bar.
3.	Go to “Customer managed keys” located on the left tab.
4.	Click “Create key”
5.	Keep key type to “Symmetric” and key usage to “Encrypt and decrypt”.
6.	Input a key alias (this will be used later in the chatbot application). Add a description and tag your resources to associate them to this project.
7.	Defining key administrative permissions is optional.
8.	Defining key usage permissions is necessary, as the KMS key policy must give your IAM user key usage permissions.
9.	Review the key configurations and click finish. Note the KMS key ID.

# Create an EC2 Instance Role (NO)
1.	Navigate to the AWS IAM console by searching for “IAM” in the AWS Management Console search bar.
2.	In the navigation pane, choose “Roles” and then choose “Create role”.
3.	Select “AWS service” under the “Trusted entity type”.
4.	From the “Use case” dropdown, select EC2.
5.	On the “Name, review, and create” page, enter a role name. Add a description and tag to associate this IAM role to the project.
6.	Choose “Create role”.

# Launch EC2 Instance
1.	Navigate to the Amazon EC2 by searching for “EC2” in the AWS Management Console search bar.
2.	Select “Launch instance”.
3.	Provide an appropriate EC2 instance name and select a QuickStart Amazon Machine Image (AMI) or create your own but ensure that selected AMI’s kernel driver is compatible with Nitro Enclaves distro kernels.
a.	For this demo, we are using the amzn2-ami-kernel-5.10-hvm-2.0.20230628.0-x86_64-gp2 AMI
4.	Select instance type.
a.	LLMs are very CPU- and memory-intensive. For this demo, we are using an r5.8xlarge instance.
5.	Configure key pair and network settings appropriately.
6.	Configure storage (I set 80GB).
a.	LLMs are very large, so ensure that there is plenty of storage so you can load and save the model directly on the EC2 instance.
7.	Use the "Advanced details" dropdown to enable Nitro Enclaves.
8.	Once the instance is running, select the instance ID and navigate to the connect button at the top for ways to connect to your instance.
9.  Attach the EC2 instance role to the EC2 instance by choosing "Actions -> Security -> Modify IAM role" and select the role you created in the previous steps.

# EC2 Instance Configuration
Now that the EC2 instance is running and you have connected to your instance, use the following steps to configure the necessary Nitro Enclave tools:
1. Follow the steps (1-5) contained here: https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave-cli-install.html to install the Nitro Enclaves CLI.
2. Install pip, Git and Docker to build docker images and download the application from GitHub. Add your instance user to the docker group (<USER> is your IAM instance user):
` sudo yum install python3-pip -y `
` sudo yum install git -y `
` sudo systemctl start docker && sudo systemctl enable docker `
3.	Start and enable the AWS Nitro Enclave allocator and vsock proxy services:
` sudo systemctl start nitro-enclaves-allocator.service && sudo systemctl enable nitro-enclaves-allocator.service `
` sudo systemctl start nitro-enclaves-vsock-proxy.service && sudo systemctl enable nitro-enclaves-vsock-proxy.service `
AWS Nitro Enclaves use a local socket connection called vsock to create a secure channel between the parent instance and the enclave.
4.	Once all the services are started and enabled, restart the instance to ensure all user groups and services are running correctly.
` sudo shutdown -r now `

# Nitro Enclave Allocator Service
AWS Nitro Enclaves are an isolated environment that designates a portion of the instance CPU and memory to run the enclave. Using the Nitro Enclave allocator service, users can indicate how many CPUs and how much memory will be taken from the parent instance to run the enclave.
1.	Modify the enclaves reserved resources using any text editor (for our solution we allocate 8 CPU and 70000 MiB memory to ensure enough resources):
` sudo nano /etc/nitro_enclaves/allocator.yaml `
2.	After editing the `cpu_count` value (and/or `memory_mib`), restart and enable the nitro-enclaves-allocator service to apply the changes:
` sudo systemctl restart nitro-enclaves-allocator.service && sudo systemctl enable nitro-enclaves-allocator.service `
Note: The `enable` command ensures the service starts automatically on boot. The `restart` command applies your configuration changes immediately.

# Clone the Project
Once the EC2 instance is configured, you can download the code that will be used to run the sensitive chatbot with an LLM inside of a Nitro Enclave:
Note: You need to update the server.py file with the appropriate KMS key id that was created in the beginning to encrypt the LLM response.
1.	Clone the GitHub project:
git clone https://<THE_REPO.git>
2.	Navigate to the project folder to build the “enclave_base” docker image that contains the Nitro Enclaves Software Development Kit (SDK) for cryptographic attestation documents from the Nitro Hypervisor (this step can take upwards to 15 minutes):
` cd /aws-nitro-enclaves-llm/src/enclave_base `
` docker build ./ -t enclave_base `

# Save the LLM in the EC2 Instance
We are using the open-source Bloom 560m large language model (LLM) for natural language processing to generate responses. This model is not fine-tuned to PII/PHI but demonstrates how a LLM can live inside of a Nitro Enclave. The model also needs to be saved on the parent instance so that it can be copied into the enclave via the Dockerfile.
1.	Navigate to the project:
` cd /aws-nitro-enclaves-llm/src/enclave `
2.	Install the necessary requirements to save the model locally:
` pip3 install -r requirements.txt `
3.	Run the save_model.py app to save the model within the /nitro_llm/enclave/bloom directory:
` python3 save_model.py `

# Build and Run the Nitro Enclave Image
To run Nitro Enclaves, an enclave image file (EIF) needs to be created from a docker image of your application. The Dockerfile located in the enclave directory contains the files, code, and LLM that will run inside of the enclave.

0. Update the KMS_KEY_ID in the Dockerfile to the KMS key ID that was created in the environment setup steps. (NO)
```
ENV KMS_KEY_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

1. Build the application docker image:
``` 
cd /aws-nitro-enclaves-llm/src/enclave 
docker build ./ -t enclave 
```

2.	Build the enclave image file as enclave.eif
` nitro-cli build-enclave --docker-uri enclave:latest --output-file enclave.eif `

When the enclave is built, a series of unique hashes and platform configuration registers (PCRs) will be created. The PCRs are a contiguous measurement to prove the identity of the hardware and application. These PCRs will be required for cryptographic attestation and used during the KMS key policy update section below.

3.	Run the enclave with the resources from the allocator.service (adding the --attach-console argument at the end will run the enclave in debug mode):
` nitro-cli run-enclave --cpu-count 8 --memory 70000 --enclave-cid 16 --eif-path enclave.eif `
Note: You need to allocate at least 4 times the EIF file size. This can be modified in the allocator.service from pervious steps.

4.	You can verify the enclave is running with the command below:
` nitro-cli describe-enclaves `

# Update the KMS Key Policy (NO)
1.	Navigate to the Amazon KMS by searching for "KMS" in the AWS Management Console search bar.
2.	Go to "Customer managed keys" located on the left tab.
3.	Search for the key that you generated in the environment setup steps.
4.	Click "Edit" on the "Key policy".
5.	Update the key policy with the enclave permissions:
~~~~
{
    "Version": "2012-10-17",
    "Id": "key-default-1",
    "Statement": [
        ...
        {
            "Sid": "Enable Enclave permissions",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<accountID>:role/<ec2instancerole>"
            },
            "Action": [
                "kms:Encrypt",
                "kms:Decrypt"
            ],
            "Resource": "*",
            "Condition": {
                "StringEqualsIgnoreCase": {
                    "kms:RecipientAttestation:PCR0": "<PCR0>",
                    "kms:RecipientAttestation:PCR1": "<PCR1>",
                    "kms:RecipientAttestation:PCR2": "<PCR2>"
                }
            }
        }
    ]
}
~~~~

# Run the Client App 
1. Navigate to `aws-nitro-enclaves-llm/src`
2. Run the client.py file:
` python client.py `

# Save the Chatbot App
To mimic a sensitive query chatbot application that lives outside of the AWS account, run the `chat.py` locally on your machine.

1. Install required modules below:
` pip install boto3 `
` pip install requests `
2. Update the KMS_ALIAS and the EC2 instance public IP in the chat.py file with the appropriate values.
3. Run the chat.py file:
` python chat.py `

NOTE: At this point I had to Grant KMS Permissions to Encrypt and Decrypt to my user 

4.	Once running, the terminal will ask for the user input and follow the architectural diagram from above to generate a secure response.

# Running the Private Question and Answer Chatbot

Now that the Nitro Enclave is up and running on the EC2 instance, you should be able to ask your chatbot PHI/PII questions. Here’s an example:
Within the Cloud9 IDE we ask our chatbot this question:

The KMS Service encrypts the question, and it will look like this:

It is then sent to the enclave and asked of the secured LLM. The question and response of the LLM will look like this:
Note: The result and encrypted response below are visible inside the enclave only in debug mode
The Result is then encrypted using KMS and is returned to the Cloud9 environment to be decrypted and will look like this:


# Cleaning Up
1.	Stop and terminate the EC2 instance created to house your Nitro Enclave.
2.	Delete the Cloud9 environment.
3.	Delete KMS Key.
4.	Remove EC2 Instance Role, IAM User Permissions.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.
