# AutoReply Bot

A [maubot](https://github.com/maubot/maubot) plugin for auto-reply bots.

## How it works

This plugin is specifically designed around the use case of a work auto-responder. I
wanted a bot to automatically reply to tell people I'm out, and optionally providing them
with some contact details for urgent matters, if someone DMs me on my work Matrix account
while I'm on holiday. When I come back, also want a summary of the DMs in which I've
missed messages.

In summary, a bot running this plugin allows you to:

* set your status to away/not away (to turn the auto-responder on and off)
* have a reply automatically sent to active DMs while away (once per DM)
* have a summary of the DMs that have been active while away when coming back

## Installation and configuration

You can install this plugin in your maubot instance using the `.mbp` file from the latest
[release](https://github.com/babolivier/matrix-autoreply/releases).

Then create a new client in maubot, connected to your own account (so it can send replies
from it). Make sure to turn "Autojoin" __off__ otherwise the bot might join new rooms and
DMs on your behalf while you're away.

You can then proceed to create a new instance with the client you have just created, and
the plugin `bzh.abolivier.autoreply`. Feel free to edit the configuration as you like. All
keys in the configuration example are required, and omitting one will cause the plugin to
malfunction.

Once the instance is running, the bot will automatically create its management room, which
is the room to use to tell it when you're away and back.

__Note:__ This plugin is meant to run on a maubot instance __you__ control. This is
because by enabling it on your own account you are effectively giving it full access to
your account, including your end-to-end encrypted messages.

## Usage

Interacting with the bot is done via the management room that is created when the instance
is first started. The following commands are available:

* `!away` marks you as away and turns the auto-responder on.
* `!back` marks you as not away and turns the auto-responder off. It also outputs a
  summary of the DMs that have been active while you were away.

## Troubleshooting

### I have accidentally left the management room

Right now there isn't a built-in recovery method for this. There are however a few ways to
make maubot recreate the room for you:

* delete the instance running the auto-reply plugin, and re-create it
* click "View database" in the instance view, then in the query input write:
  `DELETE FROM autoreply_management_rooms WHERE user_id = 'MATRIX_USER_ID'` (replace
  `MATRIX_USER_ID` with your full Matrix user ID)

The first method is much simpler and less convoluted than the second one, but also means
you will have to manually restore your configuration. So chose whichever works best for
you.