# KS54 Timetable Bot
asyncio bot that parses the site of communications college 54 named after Vostrukhin and sends the timetable to telegram in readable form.
## Main features
- asynchronous site parsing (aiohttp and beautifulsoup)
- storing data in temporary sqlite database
- regular database update (at 3:00 AM)
- the ability to find out the schedule for both the teacher and the student, for today, tomorrow or for a week
- search for the most similar group name if a mistake was made (fuzzywuzzy)
- auto-substitution of replacements and cancellations in the schedule, if any
- convenient layout and formatting
- automatic restart of the parser in case of failure, work in conditions of poor connection (relevant for this college)
## Dependencies
    pip install aiogram aiogram-dialog apscheduler beautifulsoup4 fuzzywuzzy lxml python-Levenshtein
## Starting
write your token to a variable, and just start bot. On startup, the bot will automatically update its database
