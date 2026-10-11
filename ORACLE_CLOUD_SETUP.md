# Running the trading bot 24/7 on Oracle Cloud's free tier

This moves the bot off your laptop onto a free, always-on server, so it keeps
running even when your laptop is off or asleep.

## Part 1: Things only you can do (account + server creation)

1. Go to https://www.oracle.com/cloud/free/ and sign up for an Oracle Cloud
   Free Tier account. You'll need an email, phone number, and a card for
   identity verification (you will not be charged for Always Free resources
   as long as you stay within the free limits).
2. Once logged into the Oracle Cloud Console, create a new VM instance:
   - Click the hamburger menu -> Compute -> Instances -> "Create Instance"
   - Name it something like `trading-bot-vm`
   - Under "Image and shape", choose **Ubuntu** as the OS
   - Choose the **Ampere (ARM) A1** shape and pick a size within the free
     allowance (e.g. 2 OCPUs / 12 GB RAM, well more than this bot needs)
   - Under "Add SSH keys", select "Generate a key pair for me" and
     **download both the private and public key files** -- you'll need the
     private key to connect
   - Click "Create"
3. Wait for the instance to show status "Running" (a couple of minutes).
4. Note the instance's **public IP address**, shown on its details page.
5. Under the instance's networking/security list, add an ingress rule only
   if you want to reach a dashboard remotely (optional, port 5000). The bot
   itself doesn't need any inbound ports open, it only makes outbound calls.

## Part 2: Connecting

Once you have the public IP and the downloaded private key file (something
like `ssh-key-....key`), tell me:
- the server's public IP address
- where you saved the private key file on your computer

I can then either:
- walk you through connecting via PowerShell's built-in `ssh` command yourself, or
- connect directly myself if you add this server as a saved SSH connection in
  this app (ask in the app's connection settings), after which I can set
  everything up on the server for you directly.

## Part 3: What happens once connected (I'll do this part with you)

On the server, we will:
1. Install Python 3 and pip (Ubuntu ships close to what we need already)
2. Copy over our project files (`01_fetch_data.py` through `10_auto_relearn.py`,
   and the dashboard)
3. Install the same Python packages (`ccxt`, `pandas`, `flask`, `feedparser`,
   `vaderSentiment`, etc.)
4. Set up the paper trader and auto-relearn job to run continuously using a
   process manager (`systemd` or `tmux`), so they survive you disconnecting
5. Optionally expose the dashboard so you can check on it from your laptop's
   browser by visiting the server's IP

Nothing moves until you complete Part 1, since that part needs your own
account and identity verification. Come back here once you have the IP and
key file, and we'll continue.
