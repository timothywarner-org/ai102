require('dotenv').config();
const { BotFrameworkAdapter } = require('botbuilder');
const restify = require('restify');

const adapter = new BotFrameworkAdapter({
  appId: process.env.BOT_APP_ID,
  appPassword: process.env.BOT_APP_PASSWORD
});

const server = restify.createServer();
server.listen(process.env.PORT || 3978, () => {
  console.log(`Bot listening on port ${server.address().port}`);
});

server.post('/api/messages', (req, res) => {
  adapter.processActivity(req, res, async (context) => {
    if (context.activity.type === 'message') {
      await context.sendActivity(`You said: ${context.activity.text}`);
    }
  });
});
