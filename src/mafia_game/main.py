import os
import torch
import torch.optim as optim
import torch.nn.functional as F
from mafia_game.multihead_nn import RedDQNNetwork, BlackDQNNetwork
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

# Instantiate the neural networks for the red and black teams
red_network = RedDQNNetwork(INPUT_SIZE, HIDDEN_SIZE)
black_network = BlackDQNNetwork(INPUT_SIZE, HIDDEN_SIZE)

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
        torch.save(red_network.state_dict(), os.path.join(MODEL_DIR, f"red_network_ep{episode}.pth"))
        torch.save(black_network.state_dict(), os.path.join(MODEL_DIR, f"black_network_ep{episode}.pth"))
        logger.info(f"Saved models at episode {episode}.")

logger.info("Training completed.")
