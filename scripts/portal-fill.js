const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const childProcess = require("node:child_process");
const { chromium } = require("playwright");
let transliterate = (value) => String(value ?? "");
try {
  ({ transliterate } = require("transliteration"));
} catch {
  transliterate = (value) => String(value ?? "");
}
const placeData = require("../data/nepal_places.json");
const REPORT_PATH = path.resolve(__dirname, "..", "portal-fill-report.json");

const districtToProvince = placeData.district_to_province || {};
const provinceAliases = placeData.province_aliases || {};
const countryAliases = placeData.country_aliases || {};
const commonPlaceAliases = placeData.common_place_aliases || {};
const personNameCorrections = placeData.person_name_corrections || {};
const PORTAL_CONTROL_SELECTOR = "mat-select, [role='listbox'], [role='combobox'], input:not([type=hidden]):not([type=file]), textarea, select";
const DROPDOWN_PANEL_SELECTORS = [
  ".cdk-overlay-container .mat-select-panel",
  ".cdk-overlay-container .mat-mdc-select-panel",
  ".cdk-overlay-container [role='listbox']",
  ".cdk-overlay-container .ng-dropdown-panel",
  ".cdk-overlay-container .select2-results",
  ".cdk-overlay-container .react-select__menu",
  ".cdk-overlay-container .mat-autocomplete-panel"
];
const DROPDOWN_OPTION_SELECTORS = [
  ".mat-option",
  "[role='option']",
  ".ng-option",
  ".select2-results__option",
  ".react-select__option",
  ".mat-mdc-option"
];

function keyOf(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

function compactKey(value) {
  return keyOf(value).replace(/\s+/g, "");
}

function similarity(a, b) {
  const left = compactKey(a);
  const right = compactKey(b);
  if (!left || !right) return 0;
  if (left === right) return 1;
  const matrix = Array.from({ length: left.length + 1 }, () => new Array(right.length + 1).fill(0));
  for (let i = 0; i <= left.length; i += 1) matrix[i][0] = i;
  for (let j = 0; j <= right.length; j += 1) matrix[0][j] = j;
  for (let i = 1; i <= left.length; i += 1) {
    for (let j = 1; j <= right.length; j += 1) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      );
    }
  }
  const distance = matrix[left.length][right.length];
  return 1 - (distance / Math.max(left.length, right.length));
}

function bestMatch(value, candidates) {
  const source = keyOf(value);
  let best = "";
  let bestScore = 0;
  for (const candidate of candidates) {
    const candidateKey = keyOf(candidate);
    const score = Math.max(similarity(source, candidateKey), similarity(compactKey(value), compactKey(candidate)));
    if (score > bestScore) {
      best = candidate;
      bestScore = score;
    }
  }
  return { best, score: bestScore };
}

function titleCaseWords(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(/(\s+|-)/)
    .map((token) => {
      if (!token || token === "-" || /^\s+$/.test(token)) return token;
      if (/^[A-Z0-9.]+$/.test(token) && token.length <= 4) return token.replace(/\./g, "");
      return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
    })
    .join("");
}

function simplifyAdministrativePlaceName(value) {
  return String(value || "")
    .trim()
    .replace(/\s+(Metropolitan City|Sub-Metropolitan City|Municipality|Rural Municipality|Mahanagarpalika|Upamahanagarpalika|Nagarpalika)$/i, "")
    .trim();
}

function canonicalFromTable(value, table, threshold = 0.72) {
  const text = String(value || "").trim();
  if (!text) return { value: "", confidence: 0, source: "empty", warnings: [] };
  const warnings = [];
  let working = text;
  let source = "latin";
  if (containsDevanagari(working)) {
    working = transliterate(working);
    source = "romanized";
    warnings.push("romanized_from_devanagari");
  }
  const canonicalList = Object.keys(table);
  for (const canonical of canonicalList) {
    const aliases = [canonical, ...(table[canonical] || [])];
    const direct = aliases.some((alias) => keyOf(alias) === keyOf(working) || compactKey(alias) === compactKey(working));
    if (direct) return { value: canonical, confidence: source === "latin" ? 0.98 : 0.94, source, warnings };
  }
  const { best, score } = bestMatch(working, canonicalList.flatMap((canonical) => [canonical, ...(table[canonical] || [])]));
  if (best && score >= threshold) {
    const canonical = canonicalList.find((name) => {
      const aliases = [name, ...(table[name] || [])];
      return aliases.some((alias) => keyOf(alias) === keyOf(best) || compactKey(alias) === compactKey(best));
    }) || best;
    warnings.push("fuzzy_match");
    return { value: canonical, confidence: Math.max(0.65, Math.min(0.92, 0.65 + score * 0.3)), source: "fuzzy", warnings };
  }
  return { value: titleCaseWords(working), confidence: source === "romanized" ? 0.48 : 0.55, source, warnings };
}

function normalizePlaceValue(value) {
  const canonical = canonicalFromTable(value, commonPlaceAliases);
  if (canonical.value) return { ...canonical, value: simplifyAdministrativePlaceName(canonical.value) };
  const district = canonicalFromTable(value, Object.fromEntries(Object.keys(districtToProvince).map((name) => [name, [name]])));
  if (district.value && districtToProvince[district.value]) return district;
  return canonical;
}

function normalizeProvinceValue(value) {
  return canonicalFromTable(value, provinceAliases);
}

function normalizeCountryValue(value) {
  const canonical = canonicalFromTable(value, countryAliases);
  if (keyOf(canonical.value) === "nepal") return { ...canonical, value: "Nepal" };
  if (keyOf(canonical.value) === "nepali") return { ...canonical, value: "Nepali" };
  return canonical;
}

function normalizePersonValue(value) {
  const text = String(value || "").trim();
  if (!text) return { value: "", confidence: 0, source: "empty", warnings: [] };
  let working = text;
  const warnings = [];
  let source = "latin";
  if (containsDevanagari(working)) {
    working = transliterate(working);
    source = "romanized";
    warnings.push("romanized_from_devanagari");
  }
  working = working.replace(/\./g, " ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
  const tokens = working.split(" ").map((token, index, arr) => {
    const lower = keyOf(token);
    if (personNameCorrections[lower]) return personNameCorrections[lower];
    const matched = bestMatch(token, Object.keys(personNameCorrections));
    if (matched.best && matched.score >= 0.88) return personNameCorrections[matched.best];
    return titleCaseWords(token);
  });
  const result = tokens.join(" ").replace(/\s+/g, " ").trim();
  if (/[\u0900-\u097f]/.test(result)) warnings.push("non_latin_output");
  if (/(.)\1{2,}/.test(result.toLowerCase())) warnings.push("suspicious_repetition");
  return { value: result, confidence: source === "romanized" ? 0.72 : 0.78, source, warnings };
}

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
  province: ["province", "state", "pradesh"],
  nationality: ["nationality", "citizenship", "citizen of nepal"],
  marital_status: ["marital status", "married", "single", "unmarried", "widowed", "divorced"],
  blood_group: ["blood", "blood group"],
  phone: ["mobile", "phone", "contact", "mobile number", "telephone", "फोन", "मोबाइल"],
  email: ["email", "e-mail"],
  passport_type: ["passport type", "passport pages", "available passport types", "type of passport", "ordinary", "ordinary 34 pages", "ordinary 66 pages"],
  passport_reference: ["application id", "application number", "application reference", "reference number", "registration number", "tracking number", "barcode", "passport status", "status"],
  application_reference: ["application id", "application number", "application reference", "reference number", "registration number", "tracking number", "barcode", "passport status", "status"],
  application_type: ["application type", "type of application", "application category", "new application", "renewal", "apply for passport"],
  issue_place: ["issue place", "place of issue", "issued place"],
  citizenship_issue_district: ["citizenship issue district", "issued district", "issue district"],
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
  polling_place: ["polling place"],
  temporary_address_district: ["temporary district", "current district", "present district", "temporary address district"],
  temporary_address_municipality: ["temporary municipality", "current municipality", "present municipality", "temporary address municipality"],
  temporary_address_ward: ["temporary ward", "current ward", "present ward", "temporary address ward"]
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

function containsDevanagari(value) {
  return /[\u0900-\u097f]/.test(String(value || ""));
}

function normalizePortalValue(key, value) {
  const normalized = normalizeValue(value);
  if (!normalized) return normalized;
  const field = String(key || "").toLowerCase();
  if (isDateKey(field)) return normalizeDateForInput(normalized);
  if (field.includes("ward")) return normalizeValue(normalized).replace(/[^0-9]/g, "");
  if (field.includes("nepali")) return normalized;
  if (["full_name_english", "father_name", "mother_name", "grandfather_name", "spouse_name", "guardian_name", "birth_place", "issue_place", "issued_district", "citizenship_issue_district", "address_district", "address_municipality", "province", "temporary_address_district", "temporary_address_municipality", "registration_place", "polling_place", "training_center", "bank_branch", "exam_center", "voter_area"].includes(field)) {
    const normalizedName = ["full_name_english", "father_name", "mother_name", "grandfather_name", "spouse_name", "guardian_name"].includes(field)
      ? normalizePersonValue(normalized).value
      : field === "province"
        ? normalizeProvinceValue(normalized).value
        : normalizePlaceValue(normalized).value;
    if (normalizedName) return normalizedName;
  }
  if (["nationality", "country"].includes(field)) return normalizeCountryValue(normalized).value || normalized;
  if (["gender", "marital_status", "passport_type", "application_type", "blood_group", "account_type", "license_category", "vehicle_type", "level", "service_group"].includes(field)) {
    return titleCaseWords(normalized);
  }
  if (!containsDevanagari(normalized)) return normalized;
  try {
    return normalizeValue(transliterate(normalized));
  } catch {
    return normalized;
  }
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
    Object.entries(values || {}).map(([key, value]) => [
      key,
      typeof value === "string" || typeof value === "number" ? normalizePortalValue(key, value) : value
    ])
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
  if (input.disabled) return 0;
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
  if (input.kind === "mat-select" || input.kind === "listbox" || input.kind === "combobox") score += 3;
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
  const haystack = normalizeValue(containsDevanagari(optionText) ? transliterate(optionText) : optionText).toLowerCase();
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
  return page.locator(PORTAL_CONTROL_SELECTOR).evaluateAll((nodes) =>
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
      const disabled = Boolean(
        node.disabled ||
        node.getAttribute("aria-disabled") === "true" ||
        String(node.className || "").includes("disabled")
      );
      const kind = node.tagName.toLowerCase() === "mat-select" ? "mat-select" : (node.getAttribute("role") || "");
      return {
        index,
        tag: node.tagName.toLowerCase(),
        type: node.getAttribute("type") || "",
        name: node.getAttribute("name") || "",
        id: id || "",
        kind,
        placeholder: node.getAttribute("placeholder") || "",
        ariaLabel: node.getAttribute("aria-label") || "",
        autocomplete: node.getAttribute("autocomplete") || "",
        value: node.getAttribute("value") || "",
        disabled,
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
    if (String(key).startsWith("appointment_")) continue;
    const confidence = Number(values?.field_confidence?.[key]);
    if (Number.isFinite(confidence) && confidence < 0.95) continue;
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
  const monthMap = {
    jan: 1, january: 1,
    feb: 2, february: 2,
    mar: 3, march: 3,
    apr: 4, april: 4,
    may: 5,
    jun: 6, june: 6,
    jul: 7, july: 7,
    aug: 8, august: 8,
    sep: 9, sept: 9, september: 9,
    oct: 10, october: 10,
    nov: 11, november: 11,
    dec: 12, december: 12
  };
  const iso = normalized.match(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/);
  if (iso) {
    const [, year, month, day] = iso;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  const ymd = normalized.match(/\b(\d{4})(\d{2})(\d{2})\b/);
  if (ymd) {
    const [, year, month, day] = ymd;
    return `${year}-${month}-${day}`;
  }
  const dmy = normalized.match(/\b(\d{1,2})-(\d{1,2})-(\d{4})\b/);
  if (dmy) {
    const [, day, month, year] = dmy;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  const monthName = normalized.match(/\b(\d{1,2})\s+([a-z]{3,9})\s+(\d{4})\b/i);
  if (monthName) {
    const [, day, month, year] = monthName;
    const monthNumber = monthMap[month.toLowerCase()];
    if (monthNumber) return `${year}-${String(monthNumber).padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  const monthNameReverse = normalized.match(/\b([a-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b/i);
  if (monthNameReverse) {
    const [, month, day, year] = monthNameReverse;
    const monthNumber = monthMap[month.toLowerCase()];
    if (monthNumber) return `${year}-${String(monthNumber).padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  return normalized;
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
  match = normalized.match(/\b(\d{4})(\d{2})(\d{2})\b/);
  if (match) {
    return {
      year: match[1],
      month: match[2],
      day: match[3]
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
    input.label,
    input.kind
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
  return [];
}

async function acceptPassportConsent(page, filledTargets) {
  return false;
}

async function acceptPassportConsentV2(page, filledTargets) {
  return false;
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
    const descriptor = Object.getOwnPropertyDescriptor(
      node instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      "value"
    );
    if (descriptor?.set) descriptor.set.call(node, nextValue);
    else node.value = nextValue;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    node.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }, value).catch(() => false);
}

async function openDateWidget(page, locator) {
  const opened = await locator.evaluate((node) => {
    const containers = [
      node.closest("label, .mat-form-field, .form-group, .field, .form-row, .control, .input-group, .datepicker, .calendar, td, div"),
      node.parentElement,
      node.nextElementSibling,
      node.previousElementSibling
    ].filter(Boolean);
    const selectors = [
      "button",
      "[role='button']",
      "[aria-label*='calendar' i]",
      "[title*='calendar' i]",
      "[data-testid*='calendar' i]",
      ".mat-datepicker-toggle",
      ".calendar-icon",
      ".datepicker-toggle",
      ".input-group-text"
    ];
    const textLooksDate = (text) => /calendar|date|picker/i.test(String(text || ""));
    for (const container of containers) {
      const nodes = Array.from(container.querySelectorAll(selectors.join(",")));
      for (const candidate of nodes) {
        const label = [candidate.getAttribute("aria-label"), candidate.getAttribute("title"), candidate.innerText, candidate.textContent].join(" ");
        if (textLooksDate(label) || candidate.className?.toString?.().includes("calendar") || candidate.getAttribute("data-testid")?.includes("calendar")) {
          candidate.click();
          return true;
        }
      }
    }
    const selfLabel = [node.getAttribute("aria-label"), node.getAttribute("placeholder"), node.getAttribute("title")].join(" ");
    if (textLooksDate(selfLabel)) {
      node.click();
      return true;
    }
    return false;
  }).catch(() => false);
  if (opened) return true;
  return false;
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
  const options = await locator.evaluate((node) => {
    if (!(node instanceof HTMLSelectElement)) return null;
    return Array.from(node.options).map((option) => ({
      value: option.value,
      label: option.label || option.textContent || "",
      text: option.textContent || "",
    }));
  }).catch(() => []);

  const terms = optionTerms(key, normalizedValue);
  for (const option of options || []) {
    const optionText = normalizeValue(containsDevanagari([option.value, option.label, option.text].join(" ")) ? transliterate([option.value, option.label, option.text].join(" ")) : [option.value, option.label, option.text].join(" "));
    if (optionText === normalizedValue || optionText === normalizeValue(containsDevanagari(normalizedValue) ? transliterate(normalizedValue) : normalizedValue) || terms.some((term) => term && optionText === term)) {
      return locator
        .selectOption(option.value, { timeout: 700 })
        .then(() => true)
        .catch(() => locator.selectOption({ label: option.label }, { timeout: 700 }).then(() => true).catch(() => false));
    }
  }
  return false;
}

async function waitForDropdownOptions(page, timeoutMs = 2500) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const selector of DROPDOWN_PANEL_SELECTORS) {
      const panel = page.locator(selector);
      const count = await panel.count().catch(() => 0);
      for (let index = 0; index < Math.min(count, 4); index += 1) {
        const candidate = panel.nth(index);
        if (!(await candidate.isVisible().catch(() => false))) continue;
        const optionCount = await candidate.locator(DROPDOWN_OPTION_SELECTORS.join(",")).count().catch(() => 0);
        if (optionCount > 0) return candidate;
      }
    }
    await sleep(120);
  }
  return null;
}

async function openDropdown(locator) {
  const clicked = await locator.click({ timeout: 1200 }).then(() => true).catch(() => false);
  if (clicked) return true;
  return locator.press("Space", { timeoutMs: 1200 }).then(() => true).catch(() => false);
}

async function searchOption(page, panel, value) {
  const searchFields = panel
    ? panel.locator("input:not([type=hidden]), textarea, [role='textbox']")
    : page.locator("input[placeholder*='search' i], input[aria-label*='search' i], [role='textbox']");
  const count = await searchFields.count().catch(() => 0);
  for (let index = 0; index < Math.min(count, 4); index += 1) {
    const field = searchFields.nth(index);
    if (!(await field.isVisible().catch(() => false))) continue;
    if (!(await field.isEnabled().catch(() => false))) continue;
    const text = normalizeValue(value);
    await field.fill(text, { timeout: 800 }).catch(() => null);
    return true;
  }
  return false;
}

async function selectDropdownOption(page, locator, key, value) {
  const panel = await waitForDropdownOptions(page, 3000);
  if (!panel) return false;
  await searchOption(page, panel, value);
  const optionLocator = panel.locator(DROPDOWN_OPTION_SELECTORS.join(", "));
  const count = await optionLocator.count().catch(() => 0);
  for (let index = 0; index < Math.min(count, 50); index += 1) {
    const option = optionLocator.nth(index);
    if (!(await option.isVisible().catch(() => false))) continue;
    const text = normalizeValue(await option.innerText({ timeoutMs: 700 }).catch(() => option.textContent({ timeoutMs: 700 }).catch(() => "")));
    if (!text) continue;
    if (optionTextMatches(key, value, text) || normalize(text) === normalize(value) || normalize(text) === normalize(containsDevanagari(value) ? transliterate(value) : value)) {
      const clicked = await option.click({ timeout: 1200 }).then(() => true).catch(() => false);
      if (!clicked) return false;
      await sleep(350);
      const selectedText = await locator.innerText({ timeoutMs: 700 }).catch(() => "");
      const normalizedSelected = normalizeValue(selectedText);
      const normalizedValue = normalizeValue(value);
      return Boolean(normalizedSelected && (normalizedSelected === normalizedValue || normalizedSelected.includes(normalizedValue) || normalizedValue.includes(normalizedSelected)));
    }
  }
  return false;
}

async function fillDropdown(page, locator, key, value) {
  const currentText = await locator.innerText({ timeoutMs: 700 }).catch(() => "");
  if (normalizeValue(currentText) && optionTextMatches(key, value, currentText)) return true;
  const isNativeSelect = await locator.evaluate((node) => node instanceof HTMLSelectElement).catch(() => false);
  if (isNativeSelect) return fillSelect(locator, key, value);
  const opened = await openDropdown(locator);
  if (!opened) return false;
  const selected = await selectDropdownOption(page, locator, key, value);
  if (selected) return true;
  return locator.evaluate((node) => {
    if (!node) return false;
    node.dispatchEvent(new Event("blur", { bubbles: true }));
    return false;
  }).catch(() => false);
}

async function clickVisibleText(page, text) {
  return false;
}

async function drivePassportFlow(page, values, filledTargets) {
  return [];
}

async function fillCalendarWidget(page, locator, value) {
  const parts = parseDateParts(value);
  if (!parts) return false;

  await locator.click({ timeout: 900 }).catch(() => null);
  await sleep(250);
  await openDateWidget(page, locator);
  await sleep(250);

  const popupSelectors = [
    ".mat-datepicker-content",
    ".datepicker-dropdown",
    ".bs-datepicker-container",
    ".ui-datepicker",
    "[role='dialog']",
    ".calendar",
    ".flatpickr-calendar",
    ".react-datepicker",
    ".rdp",
    ".v-datepicker",
    ".q-date"
  ];
  let popupScope = page;
  for (const selector of popupSelectors) {
    const popup = page.locator(selector);
    const count = await popup.count().catch(() => 0);
    for (let index = 0; index < Math.min(count, 4); index += 1) {
      const option = popup.nth(index);
      if (await option.isVisible().catch(() => false)) {
        popupScope = option;
        break;
      }
    }
    if (popupScope !== page) break;
  }

  const yearSelectors = [
    "select[aria-label*='year' i]",
    "select[aria-label*='वर्ष' i]",
    "select[title*='year' i]",
    ".mat-calendar-period-button",
    ".datepicker-years button",
    ".bs-datepicker-head button",
    ".calendar-years button",
    ".flatpickr-current-month",
    "button"
  ];
  const monthSelectors = [
    "select[aria-label*='month' i]",
    "select[aria-label*='महिना' i]",
    "select[title*='month' i]",
    ".datepicker-months button",
    ".bs-datepicker-head button",
    ".calendar-months button",
    ".flatpickr-monthDropdown-months",
    "button"
  ];
  const daySelectors = [
    ".mat-calendar-body-cell:not(.mat-calendar-body-disabled)",
    ".datepicker-days td:not(.disabled)",
    ".bs-datepicker-body td:not(.disabled)",
    ".flatpickr-day:not(.flatpickr-disabled)",
    ".react-datepicker__day:not(.react-datepicker__day--disabled)",
    ".calendar-days button",
    "button"
  ];

  await selectVisibleOption(popupScope, yearSelectors, parts.year) || await clickFirstVisible(popupScope, yearSelectors, parts.year);
  await sleep(150);
  for (const monthCandidate of monthCandidates(parts.month)) {
    if (await selectVisibleOption(popupScope, monthSelectors, monthCandidate) || await clickFirstVisible(popupScope, monthSelectors, monthCandidate)) break;
  }
  await sleep(150);
  await clickFirstVisible(popupScope, daySelectors, String(Number(parts.day)));
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
  const matches = findMatches(inputs, values).sort((left, right) => {
    const priority = {
      country: 1,
      passport_type: 2,
      application_type: 3,
      province: 4,
      address_district: 5,
      temporary_address_district: 6,
      address_municipality: 7,
      temporary_address_municipality: 8,
      address_ward: 9,
      temporary_address_ward: 10,
      citizenship_issue_district: 11,
      issued_district: 12,
      issue_place: 13,
      birth_place: 14,
      nationality: 15,
      gender: 16,
      marital_status: 17,
      date_of_birth: 18,
      date_of_birth_ad: 18,
      date_of_birth_bs: 18,
      issued_date: 19,
      issued_date_ad: 19,
      issued_date_bs: 19,
      expiry_date: 20,
      expiry_date_ad: 20,
      expiry_date_bs: 20
    };
    return (priority[left.key] || 100) - (priority[right.key] || 100);
  });
  const inputLocator = page.locator(PORTAL_CONTROL_SELECTOR);
  const filled = [];
  const failed = [];

  for (const best of matches) {
    const signature = fieldSignature(page, best, best.key);
    if (filledTargets.has(signature) || isSensitiveInput(best)) continue;
    const locator = inputLocator.nth(best.index);
    try {
      let didFill = false;
      if (best.type === "radio" || best.type === "checkbox") {
        didFill = await fillToggle(page, locator, best.key, best.value);
      } else if (best.kind === "mat-select" || best.kind === "listbox" || best.kind === "combobox" || best.tag === "select") {
        didFill = await fillDropdown(page, locator, best.key, best.value);
      } else {
        didFill = await fillTextOrDate(page, locator, best.key, best.value);
      }
      if (!didFill) continue;
      filledTargets.add(signature);
      filled.push({ key: best.key, value: best.value, matched: best.name || best.id || best.placeholder || best.label, url: page.url() });
      await sleep(300 + Math.floor(Math.random() * 500));
    } catch {
      failed.push({
        key: best.key,
        value: best.value,
        matched: best.name || best.id || best.placeholder || best.label,
        kind: best.kind || best.tag || "",
        url: page.url()
      });
    }
  }

  return { filled, failed };
}

async function watchAndFillPortal(context, values, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const filledTargets = new Set();
  const filled = [];
  const failed = [];

  while (Date.now() < deadline) {
    for (const page of context.pages()) {
      try {
        if (page.isClosed()) continue;
        const pageResult = await fillPage(page, values, filledTargets);
        filled.push(...pageResult.filled);
        failed.push(...pageResult.failed);
      } catch {
        // Pages can navigate, reload, or close between checks. Keep watching.
      }
    }
    await sleep(900);
  }

  return { filled, failed };
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
  let context;
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      executablePath,
      viewport: null,
      args: ["--start-maximized"]
    });
    const page = context.pages()[0] || await context.newPage();
    await page.goto(payload.url, { waitUntil: "domcontentloaded", timeout: 60000 });

    const waitForForm = payload.wait_for_form !== false;
    const waitTimeoutMs = Number(payload.wait_timeout_ms || 60 * 1000);
    const result = waitForForm
      ? await watchAndFillPortal(context, payload.values, waitTimeoutMs)
      : await fillPage(page, payload.values, new Set());

    const filled = result.filled || [];
    const failed = result.failed || [];
    const dropdownFailures = failed.filter((entry) => ["mat-select", "listbox", "combobox", "select"].includes(String(entry.kind || "").toLowerCase()));
    const dateFailures = failed.filter((entry) => isDateKey(entry.key));
    const foundCount = filled.length + failed.length;
    const completionPercent = foundCount ? Math.round((filled.length / foundCount) * 100) : 0;
    const report = {
      generated_at: new Date().toISOString(),
      url: payload.url,
      status: "open_for_review",
      filled_count: filled.length,
      failed_count: failed.length,
      completion_percent: completionPercent,
      found_count: foundCount,
      filled,
      failed,
      dropdown_failures: dropdownFailures,
      date_failures: dateFailures,
      note: filled.length
        ? "Autofill watched the connected browser and filled safe fields across available form pages. Review each page before continuing or submitting."
        : "No fillable target fields were found before the watch timeout. Keep the connected Chrome page open, navigate to the exact form page, and run autofill again."
    };

    try {
      fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
    } catch {
      // Best-effort report persistence.
    }

    console.log(JSON.stringify(report));
  } finally {
    await context?.close().catch(() => null);
  }
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
