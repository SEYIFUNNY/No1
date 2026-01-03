import express from "express";
import makeWASocket, { useMultiFileAuthState, DisconnectReason } from "baileys";
import TelegramBot from "node-telegram-bot-api";
import qrcodeTerminal from "qrcode-terminal";
import QRCode from "qrcode";
import fs from "fs";
import XLSX from "xlsx";
import { parse } from "csv-parse/sync";

// ---------------------------- CONFIG ----------------------------
const TG_TOKEN = "8269235294:AAG5cvquTJ925fXyUhk6JU_7HIshc8SdZSg"; // SABON BOT TOKEN
const OWNER_ID = 8451059379; // SABON ADMIN ID
const CHANNEL_ID = -1003517843166; // SABON CHANNEL ID
const CHANNEL_LINK = "https://t.me/wacheckproof"; // Channel link ko username
const ADMINS = [OWNER_ID];
const SUPPORT_LINK = "https://t.me/Aw0xTeamSupport";

// Payment details
const PAYMENT = {
  binanceId: "570540732",
  trc20: "TUjzhUiFGBHraDFU8tbfFCXfajoj3HwSJt"
};

// Plan definitions
const PLANS = {
  "FREE": { credits: 100, days: null, rate: 5, price: 0 },
  "$1": { credits: 200, days: 7, rate: 30, price: 1 },
  "$2": { credits: 500, days: 15, rate: 60, price: 2 },
  "$3": { credits: 1200, days: 30, rate: 120, price: 3 }
};

// ---------------------------- DATA STORAGE ----------------------------
let users = {};
let analytics = {};
let pendingPayments = {};
const USERS_FILE = "./users.json";
const ANALYTICS_FILE = "./analytics.json";
const PENDING_FILE = "./pendingPayments.json";

if (fs.existsSync(USERS_FILE)) {
  try { users = JSON.parse(fs.readFileSync(USERS_FILE, "utf8")); } catch { users = {}; }
}
if (fs.existsSync(ANALYTICS_FILE)) {
  try { analytics = JSON.parse(fs.readFileSync(ANALYTICS_FILE, "utf8")); } catch { analytics = {}; }
}
if (fs.existsSync(PENDING_FILE)) {
  try { pendingPayments = JSON.parse(fs.readFileSync(PENDING_FILE, "utf8")); } catch { pendingPayments = {}; }
}

// Rate limit storage
const rateMap = {};

// ---------------------------- CORE FUNCTIONS ----------------------------
function saveUsers() {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
}

function savePendingPayments() {
  fs.writeFileSync(PENDING_FILE, JSON.stringify(pendingPayments, null, 2));
}

function initUser(uid) {
  if (!users[uid]) {
    users[uid] = {
      plan: "FREE",
      credits: PLANS.FREE.credits,
      expiresAt: null,
      joinDate: Date.now(),
      lastDailyReset: Date.now(),
      username: ""
    };
    saveUsers();
  }
  
  // Daily credit reset for FREE users
  const user = users[uid];
  if (user.plan === "FREE") {
    const now = Date.now();
    const lastReset = user.lastDailyReset || now;
    const daysSinceReset = Math.floor((now - lastReset) / (24 * 60 * 60 * 1000));
    
    if (daysSinceReset >= 1) {
      user.credits = PLANS.FREE.credits;
      user.lastDailyReset = now;
      saveUsers();
    }
  }
}

function addPlan(uid, plan, days) {
  initUser(uid);
  users[uid].plan = plan;
  users[uid].credits += PLANS[plan].credits;
  
  if (days && days > 0) {
    users[uid].expiresAt = Date.now() + (days * 24 * 60 * 60 * 1000);
  } else {
    users[uid].expiresAt = null;
  }
  
  saveUsers();
  console.log(`✅ Plan ${plan} added for user ${uid}`);
  return users[uid];
}

function isExpired(user) {
  if (!user.expiresAt) return false;
  return Date.now() > user.expiresAt;
}

function checkAndHandleExpiry(uid) {
  const user = users[uid];
  if (!user) return false;
  
  if (isExpired(user)) {
    users[uid].plan = "FREE";
    users[uid].credits = 0;
    users[uid].expiresAt = null;
    users[uid].lastDailyReset = Date.now();
    saveUsers();
    return true;
  }
  return false;
}

function checkRateLimit(uid, plan) {
  const now = Date.now();
  const limit = PLANS[plan].rate;
  
  if (!rateMap[uid]) rateMap[uid] = [];
  rateMap[uid] = rateMap[uid].filter(t => now - t < 60000);
  
  if (rateMap[uid].length >= limit) return false;
  rateMap[uid].push(now);
  return true;
}

function logUsage(uid, count) {
  if (!analytics[uid]) analytics[uid] = { total: 0, daily: {} };
  analytics[uid].total += count;
  const day = new Date().toISOString().slice(0, 10);
  analytics[uid].daily[day] = (analytics[uid].daily[day] || 0) + count;
  fs.writeFileSync(ANALYTICS_FILE, JSON.stringify(analytics, null, 2));
}

function generatePaymentId() {
  return "PAY" + Date.now() + Math.random().toString(36).substr(2, 5).toUpperCase();
}

// ---------------------------- MESSAGE FUNCTIONS ----------------------------
async function showPlans(chatId, messageId = null) {
  const planText = `
💎 <b>PREMIUM PLANS</b>

1️⃣ <b>Basic Plan</b> - $1
   • 200 Credits
   • 7 Days Access
   • 30 checks/minute

2️⃣ <b>Standard Plan</b> - $2
   • 500 Credits
   • 15 Days Access
   • 60 checks/minute

3️⃣ <b>Premium Plan</b> - $3
   • 1200 Credits
   • 30 Days Access
   • 120 checks/minute

<b>Current FREE Plan:</b>
   • 100 Credits/day
   • 5 checks/minute

Select a plan to purchase:`;

  const keyboard = {
    inline_keyboard: [
      [{ text: "💰 Basic ($1)", callback_data: "buy_plan_$1" }, { text: "💰 Standard ($2)", callback_data: "buy_plan_$2" }],
      [{ text: "💰 Premium ($3)", callback_data: "buy_plan_$3" }],
      [{ text: "⬅️ Back to Menu", callback_data: "back_to_menu" }]
    ]
  };

  if (messageId) {
    await bot.editMessageText(planText, {
      chat_id: chatId,
      message_id: messageId,
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  } else {
    await bot.sendMessage(chatId, planText, {
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  }
}

async function showPaymentDetails(chatId, messageId, plan) {
  const planInfo = PLANS[plan];
  const paymentId = generatePaymentId();
  
  // Update user username
  if (!users[chatId]?.username) {
    try {
      const userInfo = await bot.getChat(chatId);
      users[chatId] = users[chatId] || {};
      users[chatId].username = userInfo.username || `User${chatId}`;
      saveUsers();
    } catch (err) {
      console.error("Error getting user info:", err);
    }
  }

  const username = users[chatId]?.username || `User${chatId}`;
  
  pendingPayments[paymentId] = {
    userId: chatId,
    plan: plan,
    days: planInfo.days,
    amount: planInfo.price,
    timestamp: Date.now(),
    username: username
  };
  savePendingPayments();

  const paymentText = `
💳 <b>Payment Invoice</b>

📋 <b>Order Details:</b>
• Plan: ${plan}
• Credits: ${planInfo.credits}
• Duration: ${planInfo.days} days
• Amount: $${planInfo.price}

💸 <b>Payment Methods:</b>
1. <b>Binance Pay ID:</b> <code>${PAYMENT.binanceId}</code>
2. <b>USDT (TRC20):</b> <code>${PAYMENT.trc20}</code>

📝 <b>Instructions:</b>
1. Send $${planInfo.price} using either method
2. Save transaction proof (TXID/Screenshot)
3. Click "I Paid" button below
4. Send proof to this bot

🆔 <b>Payment ID:</b> <code>${paymentId}</code>
👤 <b>User ID:</b> <code>${chatId}</code>

⚠️ <b>Note:</b> Payments are verified within 24 hours.`;

  await bot.editMessageText(paymentText, {
    chat_id: chatId,
    message_id: messageId,
    parse_mode: "HTML",
    reply_markup: {
      inline_keyboard: [
        [{ text: "✅ I Paid", callback_data: `paid_${paymentId}` }],
        [{ text: "❌ Cancel", callback_data: "cancel_payment" }]
      ]
    }
  });
}

async function showPremiumFeatures(chatId, messageId = null) {
  const features = `
🎖️ <b>PREMIUM FEATURES</b>

✅ <b>Higher Rate Limits:</b>
   • FREE: 5 checks/minute
   • Premium: 30-120 checks/minute

✅ <b>More Credits:</b>
   • FREE: 100 credits/day
   • Premium: 200-1200 credits

✅ <b>Priority Processing:</b>
   • Faster number checking
   • No delays during high traffic

✅ <b>Extended Validity:</b>
   • Premium plans last 7-30 days
   • No daily resets

✅ <b>Premium Support:</b>
   • Priority customer support
   • Quick issue resolution

🚀 <i>Unlock all these benefits by upgrading today!</i>`;

  const keyboard = {
    inline_keyboard: [
      [{ text: "💰 Buy Premium", callback_data: "premium_buy" }],
      [{ text: "⬅️ Back to Menu", callback_data: "back_to_menu" }]
    ]
  };

  if (messageId) {
    await bot.editMessageText(features, {
      chat_id: chatId,
      message_id: messageId,
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  } else {
    await bot.sendMessage(chatId, features, {
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  }
}

async function showMainMenu(chatId, messageId = null, firstName = "User") {
  initUser(chatId);
  
  let welcomeMsg = `🏆 <b>Welcome to WAProofElite!</b>\n\n`;
  welcomeMsg += `👋 Hello, <b>${firstName}</b>!\n\n`;
  welcomeMsg += `📊 <b>Your Account:</b>\n`;
  welcomeMsg += `• Plan: ${users[chatId].plan}\n`;
  welcomeMsg += `• Credits: ${users[chatId].credits}\n`;
  
  if (users[chatId].expiresAt) {
    const daysLeft = Math.ceil((users[chatId].expiresAt - Date.now()) / (24 * 60 * 60 * 1000));
    welcomeMsg += `• Premium expires in: ${daysLeft} days\n`;
  }
  
  welcomeMsg += `\n📥 Send WhatsApp numbers or upload files (.txt, .csv, .xlsx)\n\n`;
  welcomeMsg += `⚡ <b>Instant Check:</b> Verify numbers and get reports immediately.\n\n`;
  welcomeMsg += `🌐 Enjoy checking numbers like a World Cup champion!`;

  const keyboard = {
    inline_keyboard: [
      [{ text: "🎖️ Premium Features", callback_data: "premium_features" }],
      [
        { text: "💰 Buy Credits", callback_data: "buy_credits" },
        { text: "📊 My Stats", callback_data: "my_stats" }
      ],
      [
        { text: "WAProofElite Bot", url: "https://t.me/WAProofElite_bot" },
        { text: "🆘 Support", url: SUPPORT_LINK }
      ]
    ]
  };

  if (messageId) {
    await bot.editMessageText(welcomeMsg, {
      chat_id: chatId,
      message_id: messageId,
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  } else {
    await bot.sendMessage(chatId, welcomeMsg, {
      parse_mode: "HTML",
      reply_markup: keyboard
    });
  }
}

// ======================== UPDATED VERIFICATION FUNCTION ========================
async function sendToVerificationChannel(chatId, paymentId, proofText, proofPhoto = null) {
  const payment = pendingPayments[paymentId];
  if (!payment) return;
  
  const verificationMessage = `🔔 <b>NEW PAYMENT PROOF</b>\n\n` +
    `👤 <b>User:</b> ${payment.username || "Unknown"}\n` +
    `🆔 <b>User ID:</b> <code>${payment.userId}</code>\n` +
    `💎 <b>Plan:</b> ${payment.plan}\n` +
    `💰 <b>Amount:</b> $${payment.amount}\n` +
    `📝 <b>Payment ID:</b> <code>${paymentId}</code>\n` +
    `📄 <b>Details:</b> ${proofText || "See attached image"}\n\n` +
    `<b>Action:</b> Verify your wallet and choose below:`;
  
  const adminKeyboard = {
    inline_keyboard: [
      [
        { text: "✅ Confirm", callback_data: `confirm_${paymentId}` },
        { text: "❌ Reject", callback_data: `reject_${paymentId}` }
      ],
      [{ text: "👤 View Profile", url: `tg://user?id=${payment.userId}` }]
    ]
  };

  try {
    if (proofPhoto) {
      await bot.sendPhoto(CHANNEL_ID, proofPhoto, {
        caption: verificationMessage,
        parse_mode: "HTML",
        reply_markup: adminKeyboard
      });
    } else {
      await bot.sendMessage(CHANNEL_ID, verificationMessage, {
        parse_mode: "HTML",
        reply_markup: adminKeyboard
      });
    }
  } catch (error) {
    console.error("Channel Forwarding Error:", error);
    // Fallback to admin PM if channel fails
    for (const adminId of ADMINS) {
      try {
        await bot.sendMessage(adminId, `⚠️ Channel Error: ${error.message}\n\n${verificationMessage}`, {
          parse_mode: "HTML",
          reply_markup: adminKeyboard
        });
      } catch (e) {}
    }
  }
}

// ---------------------------- EXPRESS SERVER ----------------------------
const app = express();
const PORT = process.env.PORT || 3000;
app.get("/", (req, res) => res.send("✅ WAProofElite Bot is running fine!"));
app.listen(PORT, () => console.log(`🚀 Express server running on port ${PORT}`));

// ---------------------------- TELEGRAM BOT ----------------------------
const bot = new TelegramBot(TG_TOKEN, { polling: true });
let sock;
let isConnected = false;
let generatingMsgId = null;
let qrMessageId = null;
const QR_EXPIRY_TIME = 180000;

// ---------------------------- VERIFIED USERS ----------------------------
let verifiedUsers = new Set();
const VERIFIED_FILE = "./verifiedUsers.json";
if (fs.existsSync(VERIFIED_FILE)) {
  try { verifiedUsers = new Set(JSON.parse(fs.readFileSync(VERIFIED_FILE, "utf8"))); }
  catch { verifiedUsers = new Set(); }
}
function saveVerifiedUsers() {
  fs.writeFileSync(VERIFIED_FILE, JSON.stringify([...verifiedUsers], null, 2));
}

// ---------------------------- HELPER FUNCTIONS ----------------------------
function normalizeNumber(raw) {
  const n = (raw || "").toString().replace(/\D+/g, "");
  return n || null;
}

function formatNumber(num) {
  return num.startsWith("+") ? num : "+" + num;
}

async function isUserInChannel(userId) {
  try {
    const member = await bot.getChatMember(CHANNEL_ID, userId);
    return ["member", "administrator", "creator"].includes(member.status);
  } catch (error) {
    console.error("Channel check error:", error);
    return false;
  }
}

async function sendJoinMessage(chatId) {
  return bot.sendMessage(chatId, `👋 <b>Welcome to WAProofElite!</b>\n\n🔑 <b>Please join our channel to use this bot:</b>`, {
    parse_mode: "HTML",
    reply_markup: {
      inline_keyboard: [
        [{ text: "📢 Join Channel", url: CHANNEL_LINK }],
        [{ text: "✅ Verify", callback_data: "verify" }]
      ]
    }
  });
}

// ---------------------------- WHATSAPP CONNECTION ----------------------------
async function clearAuthFolder() {
  try {
    if (fs.existsSync("./auth")) {
      fs.rmSync("./auth", { recursive: true, force: true });
      console.log("Auth folder cleared");
    }
  } catch (err) {
    console.error("Error clearing auth:", err);
  }
}

async function resetAuthAndReconnect(chatId) {
  try { 
    if(sock?.ev) sock.ev.removeAllListeners(); 
    if(sock?.ws) sock.ws.close(); 
  } catch (err) {
    console.error("Error closing socket:", err);
  }
  
  isConnected = false;
  sock = null;
  const msg = await bot.sendMessage(chatId, "⏳ Generating new QR code... Please wait.");
  generatingMsgId = msg.message_id;
  setTimeout(() => connectWA(chatId), 2000);
}

async function connectWA(chatId) {
  try {
    console.log("Starting WhatsApp connection...");
    const { state, saveCreds } = await useMultiFileAuthState("./auth");
    
    sock = makeWASocket({ 
      auth: state, 
      printQRInTerminal: true,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 20000
    });
    
    sock.ev.on("creds.update", saveCreds);
    sock.ev.on("connection.update", async (update) => {
      const { qr, connection, lastDisconnect } = update;
      
      if (qr && chatId === OWNER_ID) {
        console.log("QR code generated");
        if (generatingMsgId) {
          try { await bot.deleteMessage(chatId, generatingMsgId); } catch (e) {}
          generatingMsgId = null;
        }
        qrcodeTerminal.generate(qr, { small: true });
        try {
          const buf = await QRCode.toBuffer(qr, { type: "png", width: 400 });
          const sentQR = await bot.sendPhoto(chatId, buf, { 
            caption: "📷 Scan this QR code in WhatsApp → Linked Devices.\n\n⏰ This QR will expire in 3 minutes!",
            parse_mode: "HTML"
          });
          qrMessageId = sentQR.message_id;
        } catch (err) {
          await bot.sendMessage(chatId, `QR Code:\n\n<code>${qr}</code>`, { parse_mode: "HTML" });
        }
        setTimeout(async () => {
          if (!isConnected && qrMessageId) {
            try {
              await bot.deleteMessage(chatId, qrMessageId);
              await bot.sendMessage(chatId, "❌ QR Code expired! Use /qr to generate a new one.");
            } catch (e) {}
          }
        }, QR_EXPIRY_TIME);
      }
      if (connection === "open") {
        console.log("✅ WhatsApp connected!");
        isConnected = true;
        if (qrMessageId) try { await bot.deleteMessage(chatId, qrMessageId); } catch (e) {}
        await bot.sendMessage(chatId, "✅ <b>WhatsApp Linked Successfully!</b>", { parse_mode: "HTML" });
      }
      if (connection === "close") {
        isConnected = false;
        const reason = lastDisconnect?.error?.output?.statusCode;
        if (reason === DisconnectReason.loggedOut) {
          await clearAuthFolder();
          if (chatId === OWNER_ID) await bot.sendMessage(chatId, "🔓 Logged out. Use /qr for new QR.");
        } else if (reason && chatId === OWNER_ID) {
          await bot.sendMessage(chatId, "⚠️ Connection closed. Use /qr to reconnect.");
        }
      }
    });
  } catch (err) {
    console.error("Connection error:", err);
    if (chatId === OWNER_ID) {
      await bot.sendMessage(chatId, `❌ Connection error: ${err.message}\nUse /qr to try again.`);
    }
  }
}

// ---------------------------- CHECK NUMBERS ----------------------------
async function checkNumber(num) {
  if (!isConnected || !sock) return "ERROR";
  try {
    const result = await sock.onWhatsApp(num + "@s.whatsapp.net");
    const exists = Array.isArray(result) ? !!result[0]?.exists : !!result?.exists;
    return exists ? "REGISTERED" : "NOT REGISTERED";
  } catch { return "ERROR"; }
}

async function checkNumbers(numbers, chatId) {
  initUser(chatId);
  if (checkAndHandleExpiry(chatId)) {
    await bot.sendMessage(chatId, "⛔ Premium expired. Renew to continue.", { parse_mode: "HTML" });
    return [];
  }
  const userPlan = users[chatId].plan;
  if (!checkRateLimit(chatId, userPlan)) {
    await bot.sendMessage(chatId, "⚠️ Rate limit exceeded. Wait 1 minute.", { parse_mode: "HTML" });
    return [];
  }
  const requiredCredits = numbers.length;
  if (users[chatId].credits < requiredCredits) {
    await bot.sendMessage(chatId, `❌ Insufficient credits. You need ${requiredCredits} credits, but have ${users[chatId].credits}.`, { parse_mode: "HTML" });
    return [];
  }
  let results = [];
  let progressMsg = await bot.sendMessage(chatId, `⏳ Progress: 0/${numbers.length}`);
  let done = 0;
  for (const raw of numbers) {
    const num = normalizeNumber(raw);
    if (!num) continue;
    const status = await checkNumber(num);
    results.push({ number: formatNumber(num), status });
    done++;
    try { 
      await bot.editMessageText(`⏳ Progress: ${done}/${numbers.length}`, { 
        chat_id: chatId, 
        message_id: progressMsg.message_id 
      }); 
    } catch {}
  }
  const successCount = results.filter(r => r.status !== "ERROR").length;
  if (successCount > 0) {
    users[chatId].credits -= successCount;
    saveUsers();
    logUsage(chatId, successCount);
  }
  return results;
}

async function sendResults(chatId, results) {
  if (results.length === 0) return;
  let reply = "📊 <b>WhatsApp Status Report</b>\n\n";
  for (const r of results) {
    if (r.status === "REGISTERED") reply += `✅ ${r.number}\n`;
    else if (r.status === "NOT REGISTERED") reply += `❌ ${r.number}\n`;
    else reply += `⚠️ ${r.number} Check failed\n`;
  }
  const registeredCount = results.filter(r => r.status === "REGISTERED").length;
  const notRegisteredCount = results.filter(r => r.status === "NOT REGISTERED").length;
  const failedCount = results.filter(r => !["REGISTERED","NOT REGISTERED"].includes(r.status)).length;
  reply += `\n📌 <b>Summary:</b>\n✅ Registered: ${registeredCount}\n❌ Not Registered: ${notRegisteredCount}\n⚠️ Failed: ${failedCount}\n`;
  const user = users[chatId];
  if (user) {
    reply += `\n💰 <b>Credits Left:</b> ${user.credits}`;
    if (user.expiresAt) {
      const daysLeft = Math.ceil((user.expiresAt - Date.now()) / (24 * 60 * 60 * 1000));
      reply += `\n📅 <b>Premium expires in:</b> ${daysLeft} days`;
    }
  }
  await bot.sendMessage(chatId, reply, { parse_mode: "HTML" });
}

// ---------------------------- PAYMENT FLOW ----------------------------
async function handlePaidButton(chatId, paymentId) {
  const payment = pendingPayments[paymentId];
  if (!payment) {
    return bot.sendMessage(chatId, "❌ Invalid payment ID. Please start over.", { parse_mode: "HTML" });
  }

  await bot.sendMessage(chatId, 
    `✅ <b>Payment received!</b>\n\n` +
    `📤 <b>Now send your payment proof:</b>\n` +
    `• Transaction ID (TXID) OR\n` +
    `• Screenshot of payment\n\n` +
    `Send your proof to this bot\n\n` +
    `Your Payment ID: <code>${paymentId}</code>\n` +
    `We'll verify and activate your premium soon!`,
    { parse_mode: "HTML" }
  );
}

// ---------------------------- TELEGRAM HANDLERS ----------------------------

// /start command
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  const inChannel = await isUserInChannel(chatId);
  if (!inChannel) return sendJoinMessage(chatId);
  
  if (!verifiedUsers.has(chatId)) { 
    verifiedUsers.add(chatId); 
    saveVerifiedUsers(); 
  }
  
  await showMainMenu(chatId, null, msg.from.first_name);
});

// /premium command
bot.onText(/\/premium/, async (msg) => {
  const chatId = msg.chat.id;
  const inChannel = await isUserInChannel(chatId);
  if (!inChannel) return sendJoinMessage(chatId);
  
  await showPremiumFeatures(chatId);
});

// /buy command
bot.onText(/\/buy/, async (msg) => {
  const chatId = msg.chat.id;
  const inChannel = await isUserInChannel(chatId);
  if (!inChannel) return sendJoinMessage(chatId);
  
  await showPlans(chatId);
});

// /qr command (admin only)
bot.onText(/\/qr/, async (msg) => {
  const chatId = msg.chat.id;
  if (chatId !== OWNER_ID) return bot.sendMessage(chatId, "❌ Admin only.");
  if (isConnected) return bot.sendMessage(chatId, "📱 WhatsApp is already connected.");
  await resetAuthAndReconnect(chatId);
});

// /clear command (admin only)
bot.onText(/\/clear/, async (msg) => {
  const chatId = msg.chat.id;
  if (chatId !== OWNER_ID) return bot.sendMessage(chatId, "❌ Admin only.");
  await clearAuthFolder();
  await bot.sendMessage(chatId, "✅ Auth folder cleared. Use /qr for new QR.");
});

// /confirm command (admin payment confirmation)
bot.onText(/\/confirm (\w+)/, async (msg, match) => {
  const chatId = msg.chat.id;
  if (!ADMINS.includes(chatId)) return bot.sendMessage(chatId, "❌ Admin only.");
  
  const paymentId = match[1];
  const payment = pendingPayments[paymentId];
  
  if (!payment) {
    return bot.sendMessage(chatId, "❌ Payment not found.");
  }
  
  const user = addPlan(payment.userId, payment.plan, payment.days);
  delete pendingPayments[paymentId];
  savePendingPayments();
  
  await bot.sendMessage(chatId, `✅ Payment confirmed!\nUser: ${payment.userId}\nPlan: ${payment.plan}\nCredits: ${user.credits}`, { parse_mode: "HTML" });
  
  try {
    await bot.sendMessage(payment.userId, 
      `🎉 <b>Payment Confirmed!</b>\n\n` +
      `✅ Your ${payment.plan} plan has been activated!\n` +
      `📊 Credits Added: ${PLANS[payment.plan].credits}\n` +
      `📅 Duration: ${payment.days} days\n` +
      `💰 Total Credits: ${user.credits}\n\n` +
      `You can now enjoy premium features!`,
      { parse_mode: "HTML" }
    );
  } catch (err) {
    console.error("Failed to notify user:", err);
  }
});

// /reject command (admin payment rejection)
bot.onText(/\/reject (\w+)/, async (msg, match) => {
  const chatId = msg.chat.id;
  if (!ADMINS.includes(chatId)) return bot.sendMessage(chatId, "❌ Admin only.");
  
  const paymentId = match[1];
  const payment = pendingPayments[paymentId];
  
  if (!payment) {
    return bot.sendMessage(chatId, "❌ Payment not found.");
  }
  
  delete pendingPayments[paymentId];
  savePendingPayments();
  
  await bot.sendMessage(chatId, `❌ Payment rejected!\nUser: ${payment.userId}\nPayment ID: ${paymentId}`, { parse_mode: "HTML" });
  
  try {
    await bot.sendMessage(payment.userId, 
      `❌ <b>Payment Rejected</b>\n\n` +
      `We couldn't verify your payment for ${payment.plan} plan.\n\n` +
      `⚠️ <b>Possible reasons:</b>\n` +
      `• Payment proof not clear\n` +
      `• Wrong payment amount\n` +
      `• Invalid transaction\n\n` +
      `If you believe this is a mistake, please contact support\n` +
      `Payment ID: ${paymentId}`,
      { parse_mode: "HTML" }
    );
  } catch (err) {
    console.error("Failed to notify user:", err);
  }
});

// /pending command (admin view pending payments)
bot.onText(/\/pending/, async (msg) => {
  const chatId = msg.chat.id;
  if (!ADMINS.includes(chatId)) return bot.sendMessage(chatId, "❌ Admin only.");
  
  const pending = Object.entries(pendingPayments);
  
  if (pending.length === 0) {
    return bot.sendMessage(chatId, "📭 No pending payments.", { parse_mode: "HTML" });
  }
  
  let message = `📋 <b>Pending Payments (${pending.length})</b>\n\n`;
  
  for (const [paymentId, payment] of pending) {
    const timeAgo = Math.floor((Date.now() - payment.timestamp) / (60 * 1000));
    message += `🆔 ${paymentId}\n`;
    message += `👤 ${payment.username} (${payment.userId})\n`;
    message += `💎 ${payment.plan} - $${payment.amount}\n`;
    message += `⏰ ${timeAgo} minutes ago\n\n`;
  }
  
  await bot.sendMessage(chatId, message, { parse_mode: "HTML" });
});

// ======================== UPDATED CALLBACK QUERY HANDLER ========================
bot.on("callback_query", async query => {
  const chatId = query.message.chat.id;
  const messageId = query.message.message_id;
  const data = query.data;
  
  try {
    // Check if this is from channel (message.chat.id will be CHANNEL_ID)
    const isFromChannel = query.message.chat.id === CHANNEL_ID;
    
    // 1. VERIFY BUTTON - Shows popup instead of new message
    if (data === "verify") {
      const inChannel = await isUserInChannel(query.from.id);
      
      if (inChannel) {
        verifiedUsers.add(query.from.id);
        saveVerifiedUsers();
        
        await bot.answerCallbackQuery(query.id, { 
          text: "✅ Verification successful! You can now use the bot.", 
          show_alert: false 
        });
        
        // Return to main menu
        await showMainMenu(query.from.id, null, query.from.first_name);
        
      } else {
        await bot.answerCallbackQuery(query.id, { 
          text: "⚠️ You haven't joined the channel yet! Please join first, then click Verify again.", 
          show_alert: true
        });
        return;
      }
    }
    
    // 2. ADMIN CONFIRMATION FROM CHANNEL (FIXED)
    else if (data.startsWith("confirm_")) {
      if (query.from.id !== OWNER_ID) {
        return bot.answerCallbackQuery(query.id, { 
          text: "❌ Access Denied: Owner Only", 
          show_alert: true 
        });
      }

      const paymentId = data.replace("confirm_", "");
      const payment = pendingPayments[paymentId];
      
      if (!payment) {
        return bot.answerCallbackQuery(query.id, { 
          text: "❌ Payment data not found!", 
          show_alert: true 
        });
      }

      // Activate Plan
      const user = addPlan(payment.userId, payment.plan, payment.days);
      delete pendingPayments[paymentId];
      savePendingPayments();

      // Update the Channel Message (Remove buttons and mark as approved)
      const approvedText = `✅ <b>PAYMENT APPROVED</b>\n\n` +
        `👤 User: ${payment.username}\n` +
        `🆔 User ID: <code>${payment.userId}</code>\n` +
        `💎 Plan: ${payment.plan}\n` +
        `💰 Amount: $${payment.amount}\n` +
        `📝 Payment ID: <code>${paymentId}</code>\n\n` +
        `✅ Processed by: Admin`;

      try {
        if (query.message.photo) {
          await bot.editMessageCaption(approvedText, { 
            chat_id: CHANNEL_ID, 
            message_id: query.message.message_id,
            parse_mode: "HTML"
          });
        } else {
          await bot.editMessageText(approvedText, { 
            chat_id: CHANNEL_ID, 
            message_id: query.message.message_id,
            parse_mode: "HTML"
          });
        }
      } catch (editError) {
        console.error("Edit message error:", editError);
        // If edit fails, send a new message
        await bot.sendMessage(CHANNEL_ID, approvedText, { parse_mode: "HTML" });
      }

      // Notify the User
      try {
        await bot.sendMessage(payment.userId, 
          `🎉 <b>Payment Confirmed!</b>\n\n` +
          `✅ Your ${payment.plan} plan has been activated successfully!\n\n` +
          `📊 Credits Added: ${PLANS[payment.plan].credits}\n` +
          `💰 Total Credits: ${user.credits}\n` +
          `📅 Duration: ${payment.days} days\n\n` +
          `Check /stats to see your updated account.`,
          { parse_mode: "HTML" }
        );
      } catch (notifyError) {
        console.error("Notify user error:", notifyError);
      }

      await bot.answerCallbackQuery(query.id, { 
        text: "✅ Plan activated successfully!", 
        show_alert: true 
      });
    }
    
    // 3. ADMIN REJECTION FROM CHANNEL (FIXED)
    else if (data.startsWith("reject_")) {
      if (query.from.id !== OWNER_ID) {
        return bot.answerCallbackQuery(query.id, { 
          text: "❌ Access Denied: Owner Only", 
          show_alert: true 
        });
      }

      const paymentId = data.replace("reject_", "");
      const payment = pendingPayments[paymentId];

      if (!payment) {
        return bot.answerCallbackQuery(query.id, { 
          text: "❌ Payment not found!", 
          show_alert: true 
        });
      }

      delete pendingPayments[paymentId];
      savePendingPayments();

      const rejectedText = `❌ <b>PAYMENT REJECTED</b>\n\n` +
        `👤 User: ${payment.username}\n` +
        `🆔 User ID: <code>${payment.userId}</code>\n` +
        `💎 Plan: ${payment.plan}\n` +
        `💰 Amount: $${payment.amount}\n` +
        `📝 Payment ID: <code>${paymentId}</code>\n\n` +
        `❌ Rejected by: Admin`;

      try {
        if (query.message.photo) {
          await bot.editMessageCaption(rejectedText, { 
            chat_id: CHANNEL_ID, 
            message_id: query.message.message_id,
            parse_mode: "HTML"
          });
        } else {
          await bot.editMessageText(rejectedText, { 
            chat_id: CHANNEL_ID, 
            message_id: query.message.message_id,
            parse_mode: "HTML"
          });
        }
      } catch (editError) {
        console.error("Edit message error:", editError);
        await bot.sendMessage(CHANNEL_ID, rejectedText, { parse_mode: "HTML" });
      }

      try {
        await bot.sendMessage(payment.userId, 
          `❌ <b>Payment Rejected</b>\n\n` +
          `Your payment proof for ${payment.plan} plan was not verified.\n\n` +
          `⚠️ <b>Possible reasons:</b>\n` +
          `• Payment proof not clear/visible\n` +
          `• Wrong payment amount\n` +
          `• Invalid transaction\n` +
          `• Wrong payment ID\n\n` +
          `If you believe this is a mistake, please contact @Aw0xTeamSupport\n\n` +
          `Payment ID: <code>${paymentId}</code>`,
          { parse_mode: "HTML" }
        );
      } catch (notifyError) {
        console.error("Notify user error:", notifyError);
      }

      await bot.answerCallbackQuery(query.id, { 
        text: "❌ Payment rejected!", 
        show_alert: true 
      });
    }
    
    // Regular user callbacks (from private chat)
    else if (!isFromChannel) {
      const inChannel = await isUserInChannel(chatId);
      
      if (!inChannel && !data.includes("verify")) {
        await bot.answerCallbackQuery(query.id, { 
          text: "Please join channel first!", 
          show_alert: true 
        });
        return;
      }
      
      // 4. BACK TO MENU
      if (data === "back_to_menu") {
        await showMainMenu(chatId, messageId, query.from.first_name);
        await bot.answerCallbackQuery(query.id);
      }
      
      // 5. MY STATS
      else if (data === "my_stats") {
        initUser(chatId);
        const user = users[chatId];
        let statsMsg = `📊 <b>Your Statistics</b>\n\n`;
        statsMsg += `• <b>Plan:</b> ${user.plan}\n`;
        statsMsg += `• <b>Credits:</b> ${user.credits}\n`;
        
        if (user.expiresAt) {
          const daysLeft = Math.ceil((user.expiresAt - Date.now()) / (24 * 60 * 60 * 1000));
          statsMsg += `• <b>Premium expires in:</b> ${daysLeft} days\n`;
        } else {
          statsMsg += `• <b>Premium:</b> No active plan\n`;
        }

        await bot.editMessageText(statsMsg, {
          chat_id: chatId,
          message_id: messageId,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [{ text: "⬅️ Back to Menu", callback_data: "back_to_menu" }]
            ]
          }
        });
        await bot.answerCallbackQuery(query.id);
      }
      
      // 6. PREMIUM FEATURES
      else if (data === "premium_features") {
        await showPremiumFeatures(chatId, messageId);
        await bot.answerCallbackQuery(query.id);
      }
      
      // 7. BUY CREDITS / PREMIUM BUY
      else if (data === "buy_credits" || data === "premium_buy") {
        await showPlans(chatId, messageId);
        await bot.answerCallbackQuery(query.id);
      }
      
      // 8. SELECT PLAN
      else if (data.startsWith("buy_plan_")) {
        const plan = data.replace("buy_plan_", "");
        await showPaymentDetails(chatId, messageId, plan);
        await bot.answerCallbackQuery(query.id, { text: `Selected ${plan} plan` });
      }
      
      // 9. CANCEL PURCHASE
      else if (data === "cancel_payment") {
        await showMainMenu(chatId, messageId, query.from.first_name);
        await bot.answerCallbackQuery(query.id, { text: "Purchase cancelled" });
      }
      
      // 10. I PAID BUTTON
      else if (data.startsWith("paid_")) {
        const paymentId = data.replace("paid_", "");
        await handlePaidButton(chatId, paymentId);
        await bot.answerCallbackQuery(query.id, { text: "Now send payment proof to this bot!" });
      }
      
      else {
        await bot.answerCallbackQuery(query.id);
      }
    }
    
  } catch (error) {
    console.error("Callback error:", error);
    await bot.answerCallbackQuery(query.id, { 
      text: "❌ Error occurred! Please try again.", 
      show_alert: true 
    });
  }
});

// Handle payment proof from users
bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  
  // Check if message contains payment proof
  if (msg.text && msg.text.length > 10 && !msg.text.startsWith("/")) {
    const userPending = Object.entries(pendingPayments).find(([id, payment]) => 
      payment.userId === chatId
    );
    
    if (userPending) {
      const [paymentId, payment] = userPending;
      
      if (msg.text.toLowerCase().includes("txid") || 
          msg.text.includes("hash") || 
          msg.text.includes("transaction") ||
          msg.text.length > 20) {
        
        await sendToVerificationChannel(chatId, paymentId, msg.text);
        await bot.sendMessage(chatId, 
          `✅ <b>Payment proof received!</b>\n\n` +
          `We've forwarded your proof for verification.\n` +
          `Payment ID: <code>${paymentId}</code>\n` +
          `You'll be notified once verified.`,
          { parse_mode: "HTML" }
        );
      }
    }
  }
  
  // Handle photo as payment proof
  if (msg.photo) {
    const userPending = Object.entries(pendingPayments).find(([id, payment]) => 
      payment.userId === chatId
    );
    
    if (userPending) {
      const [paymentId, payment] = userPending;
      const photoId = msg.photo[msg.photo.length - 1].file_id;
      const caption = msg.caption || "Screenshot attached";
      
      await sendToVerificationChannel(chatId, paymentId, caption, photoId);
      await bot.sendMessage(chatId, 
        `✅ <b>Payment screenshot received!</b>\n\n` +
        `We've forwarded your proof for verification.\n` +
        `Payment ID: <code>${paymentId}</code>\n` +
        `You'll be notified once verified.`,
        { parse_mode: "HTML" }
      );
    }
  }
  
  // Regular message handling (number checking)
  if (msg.text?.startsWith("/") || msg.document || !msg.text) return;
  
  const inChannel = await isUserInChannel(chatId);
  if (!inChannel) { 
    verifiedUsers.delete(chatId); 
    saveVerifiedUsers(); 
    return sendJoinMessage(chatId); 
  }
  
  if (!verifiedUsers.has(chatId)) return;

  if (!isConnected || !sock) {
    if (chatId === OWNER_ID) {
      return bot.sendMessage(chatId, "❌ WhatsApp not connected. Use /qr to generate QR code.", { parse_mode: "HTML" });
    } else {
      return bot.sendMessage(chatId, "❌ WhatsApp bot is currently unavailable. Please try again later.", { parse_mode: "HTML" });
    }
  }

  const numbers = msg.text.split(/[\n, ,]+/).map(x => x.trim()).filter(Boolean);
  if (numbers.length === 0) return;
  
  const results = await checkNumbers(numbers, chatId);
  await sendResults(chatId, results);
});

// Handle Document Uploads
bot.on("document", async msg => {
  const chatId = msg.chat.id;
  const inChannel = await isUserInChannel(chatId);
  if (!inChannel) { 
    verifiedUsers.delete(chatId); 
    saveVerifiedUsers(); 
    return sendJoinMessage(chatId); 
  }
  if (!verifiedUsers.has(chatId)) return;
  if (!isConnected || !sock) {
    if (chatId === OWNER_ID) {
      return bot.sendMessage(chatId, "❌ WhatsApp not connected. Use /qr to generate QR code.", { parse_mode: "HTML" });
    } else {
      return bot.sendMessage(chatId, "❌ WhatsApp bot is currently unavailable. Please try again later.", { parse_mode: "HTML" });
    }
  }
  try {
    const fileId = msg.document.file_id;
    const fileLink = await bot.getFileLink(fileId);
    const res = await fetch(fileLink);
    const buffer = Buffer.from(await res.arrayBuffer());
    const filePath = `./temp_${Date.now()}_${msg.document.file_name}`;
    fs.writeFileSync(filePath, buffer);
    let numbers = [];
    if (msg.document.file_name.endsWith(".txt")) {
      numbers = fs.readFileSync(filePath, "utf8").split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    } else if (msg.document.file_name.endsWith(".csv")) {
      const records = parse(fs.readFileSync(filePath), { columns: false, skip_empty_lines: true });
      numbers = records.flat().map(x => x?.toString().trim()).filter(Boolean);
    } else if (msg.document.file_name.endsWith(".xlsx") || msg.document.file_name.endsWith(".xls")) {
      const wb = XLSX.readFile(filePath);
      const sheet = wb.Sheets[wb.SheetNames[0]];
      numbers = XLSX.utils.sheet_to_json(sheet, { header: 1 }).flat().map(x => x?.toString().trim()).filter(Boolean);
    }
    fs.unlinkSync(filePath);
    if (numbers.length === 0) {
      return bot.sendMessage(chatId, "❌ No valid numbers found in the file.", { parse_mode: "HTML" });
    }
    bot.sendMessage(chatId, `📂 Total ${numbers.length} numbers received. Checking...`, { parse_mode: "HTML" });
    const results = await checkNumbers(numbers, chatId);
    await sendResults(chatId, results);
  } catch (e) { 
    console.error("File processing error:", e);
    bot.sendMessage(chatId, "❌ Error processing file.", { parse_mode: "HTML" });
  }
});

// ---------------------------- STARTUP ----------------------------
process.on("uncaughtException", err => console.error("Uncaught Exception:", err));
process.on("unhandledRejection", err => console.error("Unhandled Rejection:", err));

console.log("🤖 WAProofElite Bot started!");
console.log("💰 Payment Details:");
console.log("Binance ID:", PAYMENT.binanceId);
console.log("TRC20 Address:", PAYMENT.trc20);
console.log("📢 Verification Channel ID:", CHANNEL_ID);
console.log("👑 Owner ID:", OWNER_ID);
console.log("🔗 Support Link:", SUPPORT_LINK);
