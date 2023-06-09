import os
import pickle
from datetime import date, datetime, timedelta
from typing import Optional

import discord
from discord.ext import tasks


print('Loading', flush=True)

intents = discord.Intents.all()
client = discord.Client(command_prefix='!', intents=intents)

# Map username to {day: [cumulative, debt, debt_check, warn]}
# day: the record's date
# cumulative: how many pushups the user has done on day
# debt: how many pushups the user has missed on previous days, will accumulate first
# debt_check: whether yesterday's debt has been carried forward for this user
# warn: whether this user has been warned that time is running out for the day
data: dict = {}
msg_channel: Optional[discord.TextChannel] = None

if os.path.exists('data.pkl'):
    with open('data.pkl', 'rb') as f:
        data = pickle.load(f)
        today = str(date.today())

        for user, user_data in data.items():
            if len(user_data[today]) != 4:
                user_data[today] += [False]


def save() -> None:
    """Save the updated data to disk."""
    if data:
        with open('data.pkl', 'wb') as f:
            pickle.dump(data, f)


@client.event
async def on_ready() -> None:
    """Perform actions on startup."""
    global msg_channel
    msg_channel = discord.utils.get(client.get_all_channels(), name='general')

    await client.change_presence(activity=discord.Game(name='help! for usage'))
    await msg_channel.send('💪')
    await timed_tasks.start()


@client.event
async def on_message(message: discord.Message) -> None:
    """Perform actions when a message is sent."""
    if message.author == client.user:
        if 'Cumulative: 100' in message.content:
            await message.add_reaction('💯')
        return

    mstr: str = message.content
    today: str = str(date.today())
    user: str = message.author.name

    # If the message just contains a number (session count), log it
    if mstr.isnumeric() or mstr.startswith('-') and mstr[1:].isnumeric():
        session: int = int(message.content)

        if user not in data:
            data[user] = {}

        if today not in data[user]:
            data[user][today] = [0, 0, False, False]

        if data[user][today][0] < 100 or session < 0:

            # Pay off debt first, then accumulate new pushups
            if data[user][today][1] > 0:
                data[user][today][1] -= session

                # Carry over extra payment to cumulative
                if data[user][today][1] < 0:
                    delta = abs(data[user][today][1])
                    data[user][today][0] += delta
                    data[user][today][1] = 0

            else:
                data[user][today][0] += session

                # If cumulative goes negative, add it to debt
                if data[user][today][0] < 0:
                    delta = abs(data[user][today][0])
                    data[user][today][0] = 0
                    data[user][today][1] += delta

            # Clamp to 100 pushups for the day
            data[user][today][0] = min(100, data[user][today][0])
            response: str = f'{message.author.mention}\nSession: {session}\nCumulative: {data[user][today][0]}'

            if data[user][today][1]:
                response += f'\nDebt: {data[user][today][1]}'

            await message.channel.send(response)

        else:
            await message.channel.send(f"{message.author.mention}, stop! You're done for the day\n(Bonus session: {session})")

        await message.delete()
        save()

    # Print the help message
    elif mstr == 'help!':
        await message.channel.send('Simply send your session count in a message\nUse a negative count to undo\nUse "?" to see your stats for today.')

    # Show stats for the day for the user
    elif mstr == '?':
        await message.channel.send(f'{message.author.mention}\nYour pushups for {today}:\nCumulative: {data[user][today][0]}\nDebt: {data[user][today][1]}')


@tasks.loop(minutes=0.5)
async def timed_tasks() -> None:
    """Run scheduled tasks."""
    today: str = str(date.today())
    yesterday: str = str(date.today() - timedelta(days=1))
    hour: int = datetime.now().hour
    minute: int = datetime.now().minute

    # Carry over debt to the next day at midnight
    if hour == 0 and minute == 0:
        for user in data:
            if today not in data[user]:
                data[user][today] = [0, 0, False, False]

            if yesterday in data[user] and not data[user][yesterday][2]:
                debt = 100 - data[user][yesterday][0]
                data[user][today][1] = data[user][yesterday][1] + debt
                data[user][yesterday][2] = True

    # Snap fingers at anyone who needs to do more pushups at 11pm
    if hour == 23 and minute == 0:
        warn_msg = '🫰🫰\n'
        lacking = False

        for user in msg_channel.members:
            if user.name in data and data[user.name][today][0] < 100 and not data[user.name][today][3]:
                lack = 100 - sum(data[user.name][today][:2])
                warn_msg += f'{user.mention}! You need {lack} more pushups!\n'
                data[user.name][today][3] = True
                lacking = True

        if lacking:
            await msg_channel.send(warn_msg.strip())

with open('token.txt', 'r') as f:
    client.run(f.read())
    print('Exiting', flush=True)
    save()
