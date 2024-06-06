# Daily E-Mail Summarizer

### Program Description
This is a python script meant to be run every morning to create a summary of all of emails recieved the previous day. It uses a local LLM (currently LLama3 hosted by LMStudio) to summarize all of the emails recieved by an IMAP email address and then create an overall summary. The summary is then emailed via SMTP to the email. 

## How to Install and Run

First, clone the repository

#### LM Studio
This code relies on LM Studio's command line interface (CLI), although it would be simple to change to Ollama if that is your local LLM platform of choice. 
To access the CLI, [download LM Studio](https://lmstudio.ai/) then open your terminal and run one of these commands, depending on your operating system:
```
# Mac / Linux:
~/.cache/lm-studio/bin/lms bootstrap

# Windows:
cmd /c %USERPROFILE%/.cache/lm-studio/bin/lms.exe bootstrap
```

LM Studio allows you to download various open-souce local LLMs, the one currently used by this project is ```QuantFactory/Meta-Llama-3-8B-Instruct-GGUF```. If you use a different model, be sure to change the ```LLM_Model``` constant at the top of ```app.py```

#### .env
Create a file called ```.env``` that looks like this:

```
EMAIL="YOUR_EMAIL_HERE"
PASS="YOUR_PASSWORD_HERE"
LMS_PATH="C:\\PATH_TO_lms.exe" // Ensure this has two backslashes to separate all folders on Windows
```
with the email you want to read from and send the digest to along with its password. To get the path to the lms executable on Windows, run ```where.exe lms``` in PowerShell.

#### Requirements
Run ```$ pip install -r requirements.txt``` to install required packages

#### Scheduling
The power of this program comes from it being able to run every morning. To implement this functionality on Windows, 
1. Open Task Scheduler
2. Press "Create Task..."
3. Name it whatever you want
4. In the "Triggers" tab, select "New..."
5. Set as a daily task running at some time in the morning
6. In the "Actions" tab, select "New..."
7. In the "Action" dropdown, select "Start a program"
8. In the program/script field, enter the full path to the Python interpreter. This can be found be running ```python -c "import sys; print(sys.executable)" ``` in the Terminal
9. In the "Add arguments (optional)" field, enter the full path to ```app.py```
10. Click "OK" to save the task

To do so on Mac, it is recommended to use ```crontab``` which comes with OS by default. You can use [this website](https://crontab.guru/) to create the cronjobs scheduling command.

If you just want to run the script manually, use ```python app.py```

## Methodology
The program uses a local LLM because it can run in the backgroud on your computer without incurring API costs. The extra time that the local version takes to run doesn't matter for this application and the models are good enough at summarizing text that it didn't make sense to pay for services from OpenAI or Anthropic to do the processing. 

The program starts by reading in and doing some basic parsing/cleaning of all of the emails from the previous day via the Internet Package Access Protocol (IMAP). 

Then, the emails are fed to the LLM which generates a JSON object that includes the date, subject, sender, whether the email is a reminder, promotion, social, action, or informational, as well as a summary of pertinent information.

Once all of those JSON objects are generated, the LLM is instructed to generate a general summary of all of the emails, only including meaningful deals/promotions as well as any important reminders/information. 

This summary is then send back to your email via the Simple Mail Transfer Protocol (SMTP) for you to read. 

All of the emails are initially summarized to decrease context window usage in creating the overall summary as well as to provide an escape point for emails that just can't be understood by the LLM.


###### Developer: Bobby Miller
###### Email: robert.p.miller@vanderbilt.edu