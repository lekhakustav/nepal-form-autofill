const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const childProcess = require("node:child_process");
const { chromium } = require("playwright");

const labelAliases = {
  full_name_english: ["full name", "applicant name", "candidate name", "name as in citizenship", "name as per citizenship", "applicant's full name"],
  first_name: ["first name", "given name"],
  middle_name: ["middle name"],
  last_name: ["last name", "surname", "family name"],
  full_name_nepali: ["name in nepali", "nepali name", "नाम थर", "नेपाली नाम"],
  date_of_birth: ["date of birth", "dob", "birth date", "birth date bs", "date of birth b.s.", "जन्म मिति"],
  date_of_birth_ad: ["date of birth (a.d.)", "date of birth ad", "dob ad", "date of birth"],
  date_of_birth_bs: ["date of birth bs", "date of birth b.s.", "date of birth bs (nepali)", "date of birth nepali"],
  issued_date: ["issued date", "issue date", "date of issue", "citizenship issue date", "id issue date"],
  issued_date_ad: ["issued date (a.d.)", "issue date ad", "date of issue ad"],
  issued_date_bs: ["issued date bs", "issued date b.s.", "issue date bs", "date of issue bs", "date of issue nepali"],
  expiry_date: ["expiry date", "expiration date", "valid until", "date of expiry"],
  expiry_date_ad: ["expiry date (a.d.)", "expiry date ad", "expiration date ad"],
  expiry_date_bs: ["expiry date bs", "expiry date b.s.", "expiration date bs"],
  gender: ["gender", "sex", "लिङ्ग"],
  address_district: ["district", "permanent district", "address district", "जिल्ला"],
  address_municipality: ["municipality", "rural municipality", "local level", "vdc", "पालिका", "गा.वि.स", "नगरपालिका"],
  address_ward: ["ward", "ward no", "ward number", "वडा"],
  id_number: ["citizenship", "citizenship number", "citizenship certificate no", "national id", "nid", "identity number", "नागरिकता"],
  father_name: ["father name", "father's name", "बुबाको नाम"],
  father_first_name: ["father's first name", "father first name"],
  father_middle_name: ["father's middle name", "father middle name"],
  father_last_name: ["father's last name", "father last name", "father's surname", "father surname"],
  mother_name: ["mother name", "mother's name", "आमाको नाम"],
  mother_first_name: ["mother's first name", "mother first name"],
  mother_middle_name: ["mother's middle name", "mother middle name"],
  mother_last_name: ["mother's last name", "mother last name", "mother's surname", "mother surname"],
  spouse_name: ["spouse", "husband", "wife", "spouse name", "पति", "पत्नी"],
  spouse_first_name: ["spouse first name", "husband first name", "wife first name"],
  spouse_last_name: ["spouse last name", "spouse surname", "husband surname", "wife surname"],
  birth_place: ["place of birth", "birth place", "birth district", "district/country if born abroad", "जन्म स्थान"],
  blood_group: ["blood", "blood group"],
  phone: ["mobile", "phone", "contact", "mobile number", "telephone", "फोन", "मोबाइल"],
  email: ["email", "e-mail"],
  passport_type: ["passport type", "passport pages", "available passport types", "type of passport", "ordinary", "ordinary 34 pages", "ordinary 66 pages"],
  passport_reference: ["application id", "application number", "application reference", "reference number", "registration number", "tracking number", "barcode", "passport status", "status"],
  application_reference: ["application id", "application number", "application reference", "reference number", "registration number", "tracking number", "barcode", "passport status", "status"],
  application_type: ["application type", "type of application", "application category", "new application", "renewal", "apply for passport"],
  license_category: ["category", "license category"],
  vehicle_type: ["vehicle"],
  account_type: ["account type"],
  occupation: ["occupation"],
  education_level: ["education", "qualification"],
  post_applied: ["post", "position"],
  bank_branch: ["bank branch", "branch"],
  account_currency: ["currency"],
  institution_name: ["institution", "college", "university"],
  program: ["program", "faculty"],
  level: ["level"],
  advertisement_number: ["advertisement", "vacancy"],
  exam_center: ["exam center", "center"],
  voter_area: ["voting area", "constituency"],
  registration_place: ["registration place"],
  polling_place: ["polling place"]
};

const blockedFieldTerms = [
  "captcha",
  "recaptcha",
  "otp",
  "one time",
  "one-time",
  "verification code",
  "password",
  "passcode",
  "pin",
  "card number",
  "credit card",
  "debit card",
  "cvv",
  "cvc",
  "card expiry",
  "payment expiry",
  "payment",
  "amount",
  "submit",
  "login"
];

function normalize(text) {
  return String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function toStandardDigits(value) {
  const digitMap = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"
  };
  return String(value ?? "").replace(/[०-९٠-٩۰-۹]/g, (digit) => digitMap[digit] || digit);
}

function normalizeValue(value) {
  return toStandardDigits(value).trim();
}

function splitName(value) {
  const parts = normalizeValue(value).split(/\s+/).filter(Boolean);
  if (parts.length === 0) return {};
  if (parts.length === 1) return { first: parts[0], middle: "", last: "" };
  if (parts.length === 2) return { first: parts[0], middle: "", last: parts[1] };
  return {
    first: parts[0],
    middle: parts.slice(1, -1).join(" "),
    last: parts[parts.length - 1]
  };
}

function yearFromDate(value) {
  const match = normalizeValue(value).match(/\b(\d{4})\b/);
  return match ? Number(match[1]) : 0;
}

function splitCalendarDate(key, value, expanded) {
  const year = yearFromDate(value);
  if (!value || !year) return;
  if (year >= 2030 && !expanded[`${key}_bs`]) {
    expanded[`${key}_bs`] = value;
  } else if (year > 1900 && year < 2030 && !expanded[`${key}_ad`]) {
    expanded[`${key}_ad`] = value;
  }
}

function expandValues(values) {
  const expanded = Object.fromEntries(
    Object.entries(values || {}).map(([key, value]) => [key, typeof value === "string" || typeof value === "number" ? normalizeValue(value) : value])
  );
  const applicant = splitName(expanded.full_name_english);
  if (applicant.first && !expanded.first_name) expanded.first_name = applicant.first;
  if (applicant.middle && !expanded.middle_name) expanded.middle_name = applicant.middle;
  if (applicant.last && !expanded.last_name) expanded.last_name = applicant.last;

  const father = splitName(expanded.father_name);
  if (father.first && !expanded.father_first_name) expanded.father_first_name = father.first;
  if (father.middle && !expanded.father_middle_name) expanded.father_middle_name = father.middle;
  if (father.last && !expanded.father_last_name) expanded.father_last_name = father.last;

  const mother = splitName(expanded.mother_name);
  if (mother.first && !expanded.mother_first_name) expanded.mother_first_name = mother.first;
  if (mother.middle && !expanded.mother_middle_name) expanded.mother_middle_name = mother.middle;
  if (mother.last && !expanded.mother_last_name) expanded.mother_last_name = mother.last;

  const spouse = splitName(expanded.spouse_name);
  if (spouse.first && !expanded.spouse_first_name) expanded.spouse_first_name = spouse.first;
  if (spouse.last && !expanded.spouse_last_name) expanded.spouse_last_name = spouse.last;

  splitCalendarDate("date_of_birth", expanded.date_of_birth, expanded);
  splitCalendarDate("issued_date", expanded.issued_date, expanded);
  splitCalendarDate("expiry_date", expanded.expiry_date, expanded);
  return expanded;
}

function isSensitiveInput(input) {
  const type = normalize(input.type);
  const autocomplete = normalize(input.autocomplete);
  const text = normalize([
    input.name,
    input.id,
    input.placeholder,
    input.ariaLabel,
    input.label,
    input.nearbyText
  ].join(" "));
  if (["password", "file", "submit", "button", "reset", "hidden"].includes(type)) return true;
  if (autocomplete.includes("one-time-code") || autocomplete.includes("cc-")) return true;
  return blockedFieldTerms.some((term) => text.includes(term));
}

function scoreInput(input, key) {
  if (isSensitiveInput(input)) return 0;
  const haystack = normalize([
    input.name,
    input.id,
    input.placeholder,
    input.ariaLabel,
    input.label,
    input.nearbyText
  ].join(" "));
  const aliases = labelAliases[key] || [key.replaceAll("_", " ")];
  let score = 0;
  for (const alias of aliases) {
    const normalizedAlias = normalize(alias);
    if (normalizedAlias && haystack.includes(normalizedAlias)) score += normalizedAlias.length;
  }
  return score;
}

function optionTerms(key, value) {
  const normalized = normalizeValue(value).toLowerCase();
  const terms = [normalized];
  const optionSynonyms = {
    male: ["male", "m", "पुरुष"],
    m: ["male", "m", "पुरुष"],
    female: ["female", "f", "महिला"],
    f: ["female", "f", "महिला"],
    other: ["other", "others", "o", "अन्य"],
    new: ["new", "fresh", "first", "first time", "नयाँ"],
    renewal: ["renewal", "renew", "reissue"],
    lost: ["lost"],
    damaged: ["damaged"],
  };
  for (const term of optionSynonyms[normalized] || []) terms.push(term);
  if (key === "passport_type") {
    if (normalized.includes("34")) terms.push("ordinary 34 pages", "34 pages", "34");
    if (normalized.includes("66")) terms.push("ordinary 66 pages", "66 pages", "66");
    if (normalized.includes("ordinary")) terms.push("ordinary");
  }
  if (key === "application_type") {
    if (normalized.includes("new")) terms.push("new", "fresh", "first time", "apply");
    if (normalized.includes("renew")) terms.push("renewal", "renew", "reissue");
  }
  return [...new Set(terms.filter(Boolean))];
}

function optionTextMatches(key, value, optionText) {
  const haystack = normalizeValue(optionText).toLowerCase();
  if (!haystack) return false;
  return optionTerms(key, value).some((term) => {
    if (!term) return false;
    if (term.length === 1) return haystack.split(/\W+/).includes(term);
    return haystack.includes(term) || term.includes(haystack);
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function commandOutput(command) {
  try {
    return childProcess.execSync(command, { encoding: "utf8", windowsHide: true }).trim();
  } catch {
    return "";
  }
}

function existingPath(candidates) {
  return candidates.find((candidate) => candidate && fs.existsSync(candidate));
}

function windowsDefaultBrowserProgId() {
  if (os.platform() !== "win32") return "";
  const output = commandOutput('reg query "HKCU\\Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice" /v ProgId');
  const match = output.match(/ProgId\s+REG_\w+\s+(.+)$/im);
  return match ? match[1].trim() : "";
}

function browserExecutableFromProgId(progId) {
  const programFiles = process.env.PROGRAMFILES || "C:\\Program Files";
  const programFilesX86 = process.env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)";
  const localAppData = process.env.LOCALAPPDATA || "";
  const id = String(progId || "").toLowerCase();

  if (id.includes("chrome")) {
    return existingPath([
      process.env.CHROME_PATH,
      path.join(programFiles, "Google", "Chrome", "Application", "chrome.exe"),
      path.join(programFilesX86, "Google", "Chrome", "Application", "chrome.exe"),
      path.join(localAppData, "Google", "Chrome", "Application", "chrome.exe")
    ]);
  }

  if (id.includes("edge")) {
    return existingPath([
      process.env.EDGE_PATH,
      path.join(programFiles, "Microsoft", "Edge", "Application", "msedge.exe"),
      path.join(programFilesX86, "Microsoft", "Edge", "Application", "msedge.exe"),
      path.join(localAppData, "Microsoft", "Edge", "Application", "msedge.exe")
    ]);
  }

  if (id.includes("brave")) {
    return existingPath([
      process.env.BRAVE_PATH,
      path.join(programFiles, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
      path.join(programFilesX86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
      path.join(localAppData, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
    ]);
  }

  return "";
}

function preferredBrowserExecutable() {
  return (
    process.env.PORTAL_BROWSER_PATH ||
    browserExecutableFromProgId(windowsDefaultBrowserProgId()) ||
    existingPath([
      process.env.CHROME_PATH,
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      process.env.EDGE_PATH,
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    ])
  );
}

function safeProfileName(value) {
  return String(value || "portal-default")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "portal-default";
}

async function readInputs(page) {
  return page.locator("input:not([type=hidden]):not([type=file]), textarea, select").evaluateAll((nodes) =>
    nodes.map((node, index) => {
      const id = node.getAttribute("id");
      const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.innerText : "";
      const wrapper = node.closest("label, .form-group, .field, .form-row, .control, .col-md-3, .col-md-4, .col-md-6, .col-sm-3, .col-sm-4, .col-sm-6, .mat-form-field, td, div");
      const previous = node.previousElementSibling?.innerText || node.previousElementSibling?.textContent || "";
      const parentText = wrapper?.innerText || "";
      const next = node.nextElementSibling?.innerText || node.nextElementSibling?.textContent || "";
      const radioLabel = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.innerText || "" : "";
      const radioWrapper = node.closest("label, .mat-radio-button, .radio");
      const radioText = node.type === "radio" ? radioLabel || next || radioWrapper?.innerText || "" : "";
      return {
        index,
        tag: node.tagName.toLowerCase(),
        type: node.getAttribute("type") || "",
        name: node.getAttribute("name") || "",
        id: id || "",
        placeholder: node.getAttribute("placeholder") || "",
        ariaLabel: node.getAttribute("aria-label") || "",
        autocomplete: node.getAttribute("autocomplete") || "",
        value: node.getAttribute("value") || "",
        checked: Boolean(node.checked),
        radioText,
        label: label || "",
        nearbyText: [previous, parentText, radioText].join(" ").slice(0, 420)
      };
    })
  );
}

function findMatches(inputs, values) {
  const used = new Set();
  const matches = [];
  for (const [key, value] of Object.entries(expandValues(values))) {
    if (!value) continue;
    let best = null;
    for (const input of inputs) {
      if (used.has(input.index)) continue;
      let score = scoreInput(input, key);
      if (["radio", "checkbox"].includes(input.type) && !toggleOptionMatches(input, key, value)) score = 0;
      if (["radio", "checkbox"].includes(input.type) && toggleOptionMatches(input, key, value)) score += 100;
      if (score > 0 && (!best || score > best.score)) best = { ...input, key, value, score };
    }
    if (!best || isSensitiveInput(best)) continue;
    used.add(best.index);
    matches.push(best);
  }
  return matches;
}

function toggleOptionMatches(input, key, value) {
  const optionText = normalizeValue([input.value, input.radioText, input.label].join(" ")).toLowerCase();
  return optionTextMatches(key, value, optionText);
}

function normalizeDateForInput(value) {
  const normalized = normalizeValue(value).replace(/[./]/g, "-");
  const match = normalized.match(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/);
  if (!match) return normalized;
  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function parseDateParts(value) {
  const normalized = normalizeDateForInput(value);
  let match = normalized.match(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/);
  if (match) {
    return {
      year: match[1],
      month: match[2].padStart(2, "0"),
      day: match[3].padStart(2, "0")
    };
  }
  match = normalized.match(/\b(\d{1,2})-(\d{1,2})-(\d{4})\b/);
  if (match) {
    return {
      year: match[3],
      month: match[2].padStart(2, "0"),
      day: match[1].padStart(2, "0")
    };
  }
  return null;
}

function monthCandidates(month) {
  const number = Number(month);
  const monthNames = [
    [],
    ["january", "jan", "baishakh", "baisakh", "बैशाख"],
    ["february", "feb", "jestha", "जेठ"],
    ["march", "mar", "ashadh", "asad", "असार"],
    ["april", "apr", "shrawan", "sawan", "श्रावण"],
    ["may", "jestha", "bhadra", "भदौ"],
    ["june", "jun", "ashadh", "ashwin", "असोज"],
    ["july", "jul", "shrawan", "kartik", "कार्तिक"],
    ["august", "aug", "bhadra", "mangsir", "मंसिर"],
    ["september", "sep", "ashwin", "poush", "पुष"],
    ["october", "oct", "kartik", "magh", "माघ"],
    ["november", "nov", "mangsir", "falgun", "फागुन"],
    ["december", "dec", "poush", "chaitra", "चैत"],
  ];
  return [
    String(number),
    String(month).padStart(2, "0"),
    ...(monthNames[number] || []),
  ].filter(Boolean);
}

function isDateKey(key) {
  return /date|dob|birth|issued|issue|expiry|expiration/i.test(key);
}

function fieldSignature(page, input, key) {
  return [
    page.url(),
    key,
    input.index,
    input.name,
    input.id,
    input.placeholder,
    input.label
  ].map((part) => normalize(part)).join("|");
}

function passportTypeTerms(value) {
  const normalized = normalizeValue(value).toLowerCase();
  if (!normalized) return [];
  const terms = [normalized];
  if (normalized.includes("34")) terms.push("ordinary 34 pages", "34 pages");
  if (normalized.includes("66")) terms.push("ordinary 66 pages", "66 pages");
  if (normalized.includes("ordinary")) terms.push("ordinary");
  return [...new Set(terms)];
}

async function fillPassportServiceChoice(page, values, filledTargets) {
  const passportType = values.passport_type;
  if (!passportType) return [];
  const terms = passportTypeTerms(passportType);
  const filled = [];
  for (const term of terms) {
    const radio = page.locator("label, .radio, .mat-radio-button, div, span").filter({ hasText: term });
    const count = await radio.count().catch(() => 0);
    for (let index = 0; index < Math.min(count, 12); index += 1) {
      const option = radio.nth(index);
      if (!(await option.isVisible().catch(() => false))) continue;
      const signature = [page.url(), "passport_type", term, index].join("|");
      if (filledTargets.has(signature)) continue;
      const clicked = await option.click({ timeout: 900 }).then(() => true).catch(() => false);
      if (clicked) {
        filledTargets.add(signature);
        filled.push({ key: "passport_type", value: passportType, matched: term, url: page.url() });
        return filled;
      }
    }
  }
  return filled;
}

async function fillToggle(page, locator, key, value) {
  const optionText = await locator.evaluate((node) => {
    const id = node.getAttribute("id");
    const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.innerText || "" : "";
    const next = node.nextElementSibling?.innerText || node.nextElementSibling?.textContent || "";
    const wrapper = node.closest("label, .mat-radio-button, .mat-checkbox, .radio, .checkbox")?.innerText || "";
    return [node.getAttribute("value") || "", label, next, wrapper].join(" ");
  }).catch(() => "");
  if (!optionTextMatches(key, value, optionText)) return false;
  if (await locator.isChecked().catch(() => false)) return true;

  const checked = await locator.check({ timeout: 1200, force: true }).then(() => true).catch(() => false);
  if (checked) return true;

  const clickedLabel = await locator.evaluate((node) => {
    const id = node.getAttribute("id");
    const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
    const wrapper = node.closest("label, .mat-radio-button, .mat-checkbox, .radio, .checkbox");
    const target = label || wrapper;
    if (!target) return false;
    target.click();
    return true;
  }).catch(() => false);
  if (clickedLabel && await locator.isChecked().catch(() => true)) return true;

  return locator.evaluate((node) => {
    if (!(node instanceof HTMLInputElement)) return false;
    node.checked = true;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }).catch(() => false);
}

async function valueLooksSet(locator, expectedValue) {
  const actual = await locator.evaluate((node) => node.value || node.getAttribute("value") || "").catch(() => "");
  const normalizedActual = normalizeDateForInput(actual);
  const normalizedExpected = normalizeDateForInput(expectedValue);
  return Boolean(normalizedActual && (normalizedActual === normalizedExpected || normalizedActual.includes(normalizedExpected)));
}

async function setNativeInputValue(locator, value) {
  return locator.evaluate((node, nextValue) => {
    if (!(node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement)) return false;
    node.focus();
    node.value = nextValue;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    node.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }, value).catch(() => false);
}

async function clickFirstVisible(page, selectors, text) {
  const normalizedText = normalizeValue(text);
  for (const selector of selectors) {
    const locator = page.locator(selector).filter({ hasText: normalizedText });
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < Math.min(count, 8); index += 1) {
      const option = locator.nth(index);
      if (await option.isVisible().catch(() => false)) {
        await option.click({ timeout: 900 }).catch(() => null);
        return true;
      }
    }
  }
  return false;
}

async function selectVisibleOption(page, selectors, value) {
  for (const selector of selectors) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < Math.min(count, 8); index += 1) {
      const option = locator.nth(index);
      if (!(await option.isVisible().catch(() => false))) continue;
      const ok = await option
        .selectOption({ label: value }, { timeout: 700 })
        .then(() => true)
        .catch(() => option.selectOption(value, { timeout: 700 }).then(() => true).catch(() => false));
      if (ok) return true;
    }
  }
  return false;
}

async function fillSelect(locator, key, value) {
  const normalizedValue = isDateKey(key) ? normalizeDateForInput(value) : normalizeValue(value);
  const exact = await locator
    .selectOption({ label: normalizedValue }, { timeout: 700 })
    .then(() => true)
    .catch(() => locator.selectOption(normalizedValue, { timeout: 700 }).then(() => true).catch(() => false));
  if (exact) return true;

  const best = await locator.evaluate((node, args) => {
    if (!(node instanceof HTMLSelectElement)) return null;
    const options = Array.from(node.options).map((option) => ({
      value: option.value,
      label: option.label || option.textContent || "",
      text: option.textContent || "",
    }));
    const terms = args.terms.map((term) => String(term || "").toLowerCase());
    let bestOption = null;
    let bestScore = 0;
    for (const option of options) {
      const haystack = `${option.value} ${option.label} ${option.text}`.toLowerCase();
      let score = 0;
      for (const term of terms) {
        if (!term) continue;
        if (haystack === term) score += 100;
        else if (haystack.includes(term)) score += term.length;
      }
      if (score > bestScore) {
        bestScore = score;
        bestOption = option;
      }
    }
    return bestScore ? bestOption : null;
  }, { terms: optionTerms(key, normalizedValue) }).catch(() => null);

  if (!best) return false;
  return locator
    .selectOption(best.value, { timeout: 700 })
    .then(() => true)
    .catch(() => locator.selectOption({ label: best.label }, { timeout: 700 }).then(() => true).catch(() => false));
}

async function fillCalendarWidget(page, locator, value) {
  const parts = parseDateParts(value);
  if (!parts) return false;

  await locator.click({ timeout: 900 }).catch(() => null);
  await sleep(250);

  const yearSelectors = [
    "select[aria-label*='year' i]",
    "select[aria-label*='वर्ष' i]",
    ".mat-calendar-period-button",
    ".datepicker-years button",
    ".bs-datepicker-head button",
    ".calendar-years button",
    "button"
  ];
  const monthSelectors = [
    "select[aria-label*='month' i]",
    "select[aria-label*='महिना' i]",
    ".datepicker-months button",
    ".bs-datepicker-head button",
    ".calendar-months button",
    "button"
  ];
  const daySelectors = [
    ".mat-calendar-body-cell:not(.mat-calendar-body-disabled)",
    ".datepicker-days td:not(.disabled)",
    ".bs-datepicker-body td:not(.disabled)",
    ".calendar-days button",
    "button"
  ];

  await selectVisibleOption(page, yearSelectors, parts.year) || await clickFirstVisible(page, yearSelectors, parts.year);
  await sleep(150);
  for (const monthCandidate of monthCandidates(parts.month)) {
    if (await selectVisibleOption(page, monthSelectors, monthCandidate) || await clickFirstVisible(page, monthSelectors, monthCandidate)) break;
  }
  await sleep(150);
  await clickFirstVisible(page, daySelectors, String(Number(parts.day)));
  await sleep(200);

  if (await valueLooksSet(locator, value)) return true;
  return setNativeInputValue(locator, normalizeDateForInput(value));
}

async function fillTextOrDate(page, locator, key, value) {
  const fillValue = isDateKey(key) ? normalizeDateForInput(value) : normalizeValue(value);
  try {
    await locator.fill(fillValue, { timeout: 1500 });
    if (!isDateKey(key) || await valueLooksSet(locator, fillValue)) return true;
  } catch {
    // Readonly date fields often open a calendar instead of accepting typing.
  }
  if (isDateKey(key) && await fillCalendarWidget(page, locator, fillValue)) return true;
  return setNativeInputValue(locator, fillValue);
}

async function fillPage(page, values, filledTargets) {
  const inputs = await readInputs(page);
  const matches = findMatches(inputs, values);
  const inputLocator = page.locator("input:not([type=hidden]):not([type=file]), textarea, select");
  const filled = await fillPassportServiceChoice(page, values, filledTargets);

  for (const best of matches) {
    const signature = fieldSignature(page, best, best.key);
    if (filledTargets.has(signature) || isSensitiveInput(best)) continue;
    const locator = inputLocator.nth(best.index);
    try {
      let didFill = false;
      if (best.type === "radio" || best.type === "checkbox") {
        didFill = await fillToggle(page, locator, best.key, best.value);
      } else if (best.tag === "select") {
        didFill = await fillSelect(locator, best.key, best.value);
      } else {
        didFill = await fillTextOrDate(page, locator, best.key, best.value);
      }
      if (!didFill) continue;
      filledTargets.add(signature);
      filled.push({ key: best.key, value: best.value, matched: best.name || best.id || best.placeholder || best.label, url: page.url() });
    } catch {
      // Skip fields that the portal blocks, masks, or formats itself.
    }
  }

  return filled;
}

async function watchAndFillPortal(context, values, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const filledTargets = new Set();
  const filled = [];

  while (Date.now() < deadline) {
    for (const page of context.pages()) {
      try {
        if (page.isClosed()) continue;
        const pageFilled = await fillPage(page, values, filledTargets);
        filled.push(...pageFilled);
      } catch {
        // Pages can navigate, reload, or close between checks. Keep watching.
      }
    }
    await sleep(900);
  }

  return filled;
}

async function main() {
  const raw = fs.readFileSync(0, "utf8");
  const payload = JSON.parse(raw);
  const profileName = safeProfileName(payload.browser_profile);
  const userDataDir = process.env.PORTAL_CHROME_PROFILE || path.resolve(__dirname, "..", ".portal-chrome-profiles", profileName);
  const executablePath = preferredBrowserExecutable();
  if (!executablePath) {
    throw new Error("No supported Chromium browser found. Install Chrome or Edge, or set PORTAL_BROWSER_PATH.");
  }
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    executablePath,
    viewport: null,
    args: ["--start-maximized"]
  });
  const page = context.pages()[0] || await context.newPage();
  await page.goto(payload.url, { waitUntil: "domcontentloaded", timeout: 60000 });

  const waitForForm = payload.wait_for_form !== false;
  const waitTimeoutMs = Number(payload.wait_timeout_ms || 60 * 1000);
  const filled = waitForForm
    ? await watchAndFillPortal(context, payload.values, waitTimeoutMs)
    : await fillPage(page, payload.values, new Set());

  console.log(JSON.stringify({
    status: "open_for_review",
    filled_count: filled.length,
    filled,
    note: filled.length
      ? "Autofill watched the connected browser and filled safe fields across available form pages. Review each page before continuing or submitting."
      : "No fillable target fields were found before the watch timeout. Keep the connected Chrome page open, navigate to the exact form page, and run autofill again."
  }));
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
