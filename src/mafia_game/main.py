import os
import torch
import torch.optim as optim
import torch.nn.functional as F
from mafia_game.multihead_nn import RedTransformerNetwork, BlackTransformerNetwork
from mafia_game.train import train
from mafia_game.logger import logger

# Constants
INPUT_SIZE = 7154  # Adjust this based on your game state size
HIDDEN_SIZE = 128  # Adjust this based on your network design
NUM_EPISODES = 10000  # Number of episodes to train
GAMMA = 0.99  # Discount factor for future rewards
SAVE_INTERVAL = 100  # Save the model every 100 episodes
LOG_INTERVAL = 10  # Log progress every 10 episodes
MODEL_DIR = "models"  # Directory to save models

# Ensure the model directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

red_network_path = os.path.join(MODEL_DIR, "red_network.pth")
black_network_path = os.path.join(MODEL_DIR, "black_network.pth")

if os.path.exists(red_network_path) and os.path.exists(black_network_path):
    # Load pre-trained models
    red_network = RedTransformerNetwork(INPUT_SIZE, HIDDEN_SIZE)
    red_network.load_state_dict(torch.load(red_network_path))
    black_network = BlackTransformerNetwork(INPUT_SIZE, HIDDEN_SIZE)
    black_network.load_state_dict(torch.load(black_network_path))
    logger.info("Loaded pre-trained models.")
else:
    # Instantiate new neural networks
    red_network = RedTransformerNetwork(INPUT_SIZE, HIDDEN_SIZE)
    black_network = BlackTransformerNetwork(INPUT_SIZE, HIDDEN_SIZE)
    logger.info("Created new models.")

# Optimizers
red_optimizer = optim.Adam(red_network.parameters())
black_optimizer = optim.Adam(black_network.parameters())

# Loss function
loss_function = F.mse_loss

with open(
        "/home/ANT.AMAZON.COM/zedmor/PycharmProjects/mafia_modeling/src/mafia_game/logs/loss_file.log",
        "w",
        ) as loss_file:
    loss_file.write("Starting session")

# Training loop
for episode in range(NUM_EPISODES):
    # Run the training episode
    train(
        red_network,
        black_network,
        red_optimizer,
        black_optimizer,
        loss_function,
        1,  # Train for 1 episode at a time
        gamma=GAMMA,
    )

    # Log progress
    if episode % LOG_INTERVAL == 0:
        logger.info(f"Episode {episode}/{NUM_EPISODES} completed.")

    # Save the model
    if episode % SAVE_INTERVAL == 0:
        torch.save(red_network.state_dict(), os.path.join(MODEL_DIR, f"red_network.pth"))
        torch.save(black_network.state_dict(), os.path.join(MODEL_DIR, f"black_network.pth"))
        logger.info(f"Saved models at episode {episode}.")

logger.info("Training completed.")
