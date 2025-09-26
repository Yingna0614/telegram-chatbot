# telegram-chatbot
Building a Telegram chatbot is easy and fun! Using BotFather and Python, I made a bot that can answer questions, summarize webpages, analyze PDFs or Word files, and even explain images. It keeps track of conversations, responding in real time like a smart study buddy. Anyone can try it and see how simple it is to turn ideas into a helpful bot!

# Telegram Chatbot Setup Guide

This guide will help you set up a Telegram chatbot powered by a large language model using OpenRouter.  

## Step 1: Create a Telegram Bot using BotFather
1. Open Telegram and search for **BotFather**.  
2. Start a chat and use the command:  
```

/newbot

```
3. Complete the setup and receive your **bot token**. Save it for later.  

## Step 2: Set Up OpenRouter
Currently, I used openrouter and gpt-4o. you can change the model and router based on your own need.
1. Go to [OpenRouter](https://openrouter.ai/) and log in.  
2. Navigate to the **API** section to create a new API key.  
3. Save the API key for later use.  


## Step 3: Implement Bot Functions (group chatbot or individual chatbot)
The following key functions are already implemented:  
- **Text Handling**: Respond to incoming text messages using the LLM.  
- **Link Handling**: Parse and respond to links sent by users.  
- **Document Handling**: Upload and analyze PDF or Word documents.  
- **Image Analysis**: Analyze images sent by users.  

You can modify the code to fit your specific needs.  (see chatbot-code.py for more details)
 

## Step 4: Crawl Data from Telegram for analysis (Optional)
1. Register for **API ID** and **API Hash** at [my.telegram.org](https://my.telegram.org/auth).  
2. Update the ID and hash in this Colab notebook: [Telegram Data Crawling Colab](https://colab.research.google.com/drive/1ldN-8_07g3GA_BKGItFEI3r5hIP5m-sw?usp=sharing)  
3. Modify the code as needed for your data collection requirements.  


