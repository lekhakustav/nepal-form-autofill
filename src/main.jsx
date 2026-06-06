import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BadgeCheck,
  Check,
  ChevronLeft,
  ClipboardCheck,
  Download,
  ExternalLink,
  FileScan,
  FileText,
  IdCard,
  Loader2,
  LockKeyhole,
  MousePointerClick,
  Printer,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const formTypes = [
  { id: "passport", title: "Passport Application", nepali: "राहदानी आवेदन", icon: FileText, accent: "red" }
];

const fieldLabels = {
  full_name_english: ["Full name", "पूरा नाम"],
  full_name_nepali: ["Name in Nepali", "नेपाली नाम"],
  date_of_birth: ["Date of birth", "जन्म मिति"],
  gender: ["Gender", "लिङ्ग"],
  address_district: ["District", "जिल्ला"],
  address_municipality: ["Municipality / Rural Municipality", "पालिका"],
  address_ward: ["Ward no.", "वडा नं."],
  id_number: ["Citizenship / NID number", "नागरिकता / राष्ट्रिय परिचयपत्र नं."],
  father_name: ["Father's name", "बुबाको नाम"],
  mother_name: ["Mother's name", "आमाको नाम"],
  grandfather_name: ["Grandfather's name", "हजुरबुबाको नाम"],
  spouse_name: ["Spouse name", "पति / पत्नीको नाम"],
  blood_group: ["Blood group", "रक्त समूह"],
  issued_district: ["Issued district", "जारी जिल्ला"],
  issued_date: ["Issued date", "जारी मिति"],
  expiry_date: ["Expiry / valid until", "मान्य मिति"],
  passport_type: ["Passport type", "राहदानीको किसिम"],
  application_type: ["Application type", "आवेदनको किसिम"],
  birth_place: ["Place of birth", "जन्म स्थान"],
  old_passport_number: ["Previous passport no.", "पुरानो राहदानी नं."],
  license_category: ["License category", "अनुमतिपत्र वर्ग"],
  vehicle_type: ["Vehicle type", "सवारी साधनको किसिम"],
  training_center: ["Training center", "प्रशिक्षण केन्द्र"],
  bank_branch: ["Bank branch", "बैंक शाखा"],
  account_currency: ["Currency", "मुद्रा"],
  phone: ["Mobile number", "मोबाइल नं."],
  email: ["Email address", "इमेल"],
  occupation: ["Occupation", "पेशा"],
  income_source: ["Source of income", "आय स्रोत"],
  education_level: ["Education level", "शैक्षिक योग्यता"],
  institution_name: ["Institution name", "संस्थाको नाम"],
  account_type: ["Account type", "खाता प्रकार"],
  faculty: ["Faculty", "संकाय"],
  guardian_name: ["Guardian name", "अभिभावकको नाम"],
  program: ["Program / Faculty", "कार्यक्रम / संकाय"],
  level: ["Level", "तह"],
  post_applied: ["Position applied for", "आवेदन गरिएको पद"],
  service_group: ["Service / group", "सेवा / समूह"],
  advertisement_number: ["Advertisement no.", "विज्ञापन नं."],
  exam_center: ["Exam center", "परीक्षा केन्द्र"],
  voter_area: ["Voting area", "मतदान क्षेत्र"],
  registration_place: ["Registration place", "दर्ता स्थान"],
  polling_place: ["Polling place", "मतदान स्थल"]
};

const formConfigs = {
  passport: ["application_type", "passport_type", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "birth_place", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "spouse_name", "old_passport_number", "phone", "email"],
  driving_license: ["application_type", "license_category", "vehicle_type", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "blood_group", "training_center", "phone", "email"],
  bank_account: ["bank_branch", "account_type", "account_currency", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "occupation", "income_source", "phone", "email"],
  admission: ["institution_name", "program", "faculty", "level", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "guardian_name", "education_level", "phone", "email"],
  voter_registration: ["registration_place", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "voter_area", "polling_place", "phone"],
  government_job: ["advertisement_number", "post_applied", "service_group", "level", "exam_center", "full_name_english", "full_name_nepali", "date_of_birth", "issued_date", "expiry_date", "gender", "address_district", "address_municipality", "address_ward", "id_number", "issued_district", "father_name", "mother_name", "education_level", "phone", "email"]
};

const sheetTemplates = {
  passport: {
    office: "Government of Nepal, Department of Passports",
    title: "Passport Application Form",
    note: "Machine readable / e-passport applicant details",
    sections: [
      ["Application Details", ["application_type", "passport_type", "old_passport_number"]],
      ["Applicant Details", ["full_name_english", "full_name_nepali", "date_of_birth", "birth_place", "gender"]],
      ["Citizenship / NID Details", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Family and Contact", ["father_name", "mother_name", "spouse_name", "phone", "email"]]
    ]
  },
  driving_license: {
    office: "Government of Nepal, Department of Transport Management",
    title: "Driving License Application Form",
    note: "New / add category / renewal applicant details",
    sections: [
      ["License Request", ["application_type", "license_category", "vehicle_type", "training_center"]],
      ["Applicant Details", ["full_name_english", "full_name_nepali", "date_of_birth", "gender", "blood_group"]],
      ["Identity and Address", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Family and Contact", ["father_name", "mother_name", "phone", "email"]]
    ]
  },
  bank_account: {
    office: "Nepal Banking KYC / Account Opening",
    title: "Personal Account Opening Form",
    note: "Customer information and KYC details",
    sections: [
      ["Account Details", ["bank_branch", "account_type", "account_currency"]],
      ["Personal Details", ["full_name_english", "full_name_nepali", "date_of_birth", "gender", "occupation", "income_source"]],
      ["Identity and Address", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Family and Contact", ["father_name", "mother_name", "phone", "email"]]
    ]
  },
  admission: {
    office: "College / University Admission Office",
    title: "Student Admission Application Form",
    note: "Academic admission applicant details",
    sections: [
      ["Program Details", ["institution_name", "program", "faculty", "level"]],
      ["Student Details", ["full_name_english", "full_name_nepali", "date_of_birth", "gender", "education_level"]],
      ["Identity and Address", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Guardian and Contact", ["father_name", "mother_name", "guardian_name", "phone", "email"]]
    ]
  },
  voter_registration: {
    office: "Election Commission, Nepal",
    title: "Voter Registration Form",
    note: "Electoral roll personal detail collection",
    sections: [
      ["Registration Details", ["registration_place", "voter_area", "polling_place"]],
      ["Applicant Details", ["full_name_english", "full_name_nepali", "date_of_birth", "gender"]],
      ["Identity and Permanent Address", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Family and Contact", ["father_name", "mother_name", "phone"]]
    ]
  },
  government_job: {
    office: "Public Service / Government Recruitment",
    title: "Government Job Application Form",
    note: "Vacancy application applicant details",
    sections: [
      ["Vacancy Details", ["advertisement_number", "post_applied", "service_group", "level", "exam_center"]],
      ["Applicant Details", ["full_name_english", "full_name_nepali", "date_of_birth", "gender", "education_level"]],
      ["Identity and Address", ["id_number", "issued_date", "expiry_date", "issued_district", "address_district", "address_municipality", "address_ward"]],
      ["Family and Contact", ["father_name", "mother_name", "phone", "email"]]
    ]
  }
};

const sampleMaster = {
  id_type: "CITIZENSHIP",
  full_name_english: "Sita Shrestha",
  full_name_nepali: "सीता श्रेष्ठ",
  date_of_birth: "2058-04-12",
  gender: "Female",
  permanent_address: {
    district: "Kathmandu",
    municipality: "Kathmandu Metropolitan City",
    ward: "12"
  },
  citizenship_number: "27-01-78-12345",
  nid_number: null,
  issued_district: "Kathmandu",
  issued_date: "2078-03-20",
  expiry_date: "",
  father_name: "Ram Shrestha",
  mother_name: "Maya Shrestha",
  grandfather_name: "Hari Shrestha",
  spouse_name: "",
  blood_group: "B+"
};

const defaultsByForm = {
  passport: { application_type: "New", passport_type: "Ordinary 34 pages", birth_place: "Kathmandu" },
  driving_license: { application_type: "New", license_category: "A/B", vehicle_type: "Motorcycle / Car", training_center: "Kathmandu" },
  bank_account: { bank_branch: "Kathmandu Main Branch", account_type: "Savings", account_currency: "NPR", occupation: "Student", income_source: "Family support" },
  admission: { institution_name: "Tribhuvan University", program: "Bachelor", faculty: "Management", level: "Undergraduate", guardian_name: "Ram Shrestha", education_level: "+2 Passed" },
  voter_registration: { registration_place: "Kathmandu", voter_area: "Kathmandu-5", polling_place: "Ward Office" },
  government_job: { advertisement_number: "PSC-2081-82", post_applied: "Assistant", service_group: "Administration", level: "Level 5", exam_center: "Kathmandu", education_level: "Bachelor" }
};

const portalGuides = {
  passport: [
    {
      title: "Online Pre-Enrollment Form",
      url: "https://emrtds.nepalpassport.gov.np/",
      note: "For a new e-passport application. Fill the online form, submit it yourself, then save the PDF receipt or appointment slip."
    },
    {
      title: "Passport Status Check",
      url: "https://emrtds.nepalpassport.gov.np/",
      note: "For an existing application. Use the Application ID / reference number from SMS, email, PDF receipt, appointment slip, or payment receipt."
    },
    {
      title: "Passport department website",
      url: "https://nepalpassport.gov.np/en",
      note: "Use this if the direct ePassport portal is down or you need official instructions first."
    }
  ],
  driving_license: [
    {
      title: "DoTM online driving license",
      url: "https://applydlnew.dotm.gov.np/",
      note: "Starts with mobile number and CAPTCHA. Finish login/CAPTCHA manually, then run autofill on the form page."
    }
  ],
  admission: [
    {
      title: "MEC entrance application",
      url: "https://entrance.mec.gov.np/",
      note: "For medical education common entrance forms such as MECEE."
    },
    {
      title: "TU Faculty of Education entrance",
      url: "https://entrance.tufoe.edu.np/",
      note: "One TU entrance portal example. Other campuses/faculties may use separate portals."
    }
  ],
  voter_registration: [
    {
      title: "Election Commission voter pre-registration",
      url: "https://applyvr.election.gov.np/Login/Preregistration/EnterMobileNo",
      note: "Supports NIN verification and voter pre-registration."
    },
    {
      title: "Election Commission website",
      url: "https://election.gov.np/",
      note: "Use this for notices, voter list, and if the direct form changes."
    }
  ],
  government_job: [
    {
      title: "PSC online application",
      url: "https://psconline1.psc.gov.np/",
      note: "For Lok Sewa/Public Service Commission online applications."
    },
    {
      title: "PSC official website",
      url: "https://psc.gov.np/",
      note: "Use this to find notices and confirm the latest application link."
    }
  ]
};

const portalSearches = {
  passport: "Nepal ePassport online application emrtds official",
  driving_license: "Nepal online driving license application DoTM official",
  admission: "Nepal college university entrance online application official portal",
  voter_registration: "Nepal voter registration pre registration Election Commission official",
  government_job: "Nepal PSC online application Lok Sewa official"
};

function flattenMaster(master = {}) {
  return {
    full_name_english: master.full_name_english || "",
    full_name_nepali: master.full_name_nepali || "",
    date_of_birth: master.date_of_birth || "",
    gender: master.gender || "",
    address_district: master.permanent_address?.district || "",
    address_municipality: master.permanent_address?.municipality || "",
    address_ward: master.permanent_address?.ward || "",
    id_number: master.citizenship_number || master.nid_number || "",
    father_name: master.father_name || "",
    mother_name: master.mother_name || "",
    grandfather_name: master.grandfather_name || "",
    spouse_name: master.spouse_name || "",
    blood_group: master.blood_group || "",
    issued_district: master.issued_district || "",
    issued_date: master.issued_date || "",
    expiry_date: master.expiry_date || ""
  };
}

function sourceText(idType) {
  if (idType === "NID") return "Filled from NID";
  if (idType === "SAMPLE") return "Sample autofill";
  return "Filled from Citizenship Card";
}

function applyMasterToForm(formId, master) {
  const flattened = { ...flattenMaster(master), ...(defaultsByForm[formId] || {}) };
  const initialValues = {};
  const sourceMap = {};
  formConfigs[formId].forEach((field) => {
    initialValues[field] = flattened[field] || "";
    sourceMap[field] = Boolean(flattened[field]);
  });
  return { initialValues, sourceMap };
}

function formatNumber(value) {
  return new Intl.NumberFormat("en").format(Number(value || 0));
}

function UsagePanel({ usage, onRefresh }) {
  const data = usage?.usage || {};
  const limits = usage?.limits || {};
  const links = usage?.links || {};
  const rpmLimit = limits.local_gemini_rpm_limit || 0;
  const rpmUsed = limits.local_gemini_rpm_used || 0;
  const rpmText = rpmLimit ? `${rpmUsed}/${rpmLimit} this minute` : "Not set";

  return (
    <div className="usage-panel">
      <div className="usage-head">
        <div>
          <h3>Usage & limits</h3>
          <p>Shows this app's local Gemini extraction and portal-fill usage.</p>
        </div>
        <button className="icon-button" onClick={onRefresh} title="Refresh usage">
          <Activity size={18} />
        </button>
      </div>
      <div className="usage-grid">
        <span><strong>{formatNumber(data.ocr_scans)}</strong> OCR scans today</span>
        <span><strong>{formatNumber(data.gemini_calls)}</strong> Gemini calls</span>
        <span><strong>{formatNumber(data.total_tokens)}</strong> total tokens</span>
        <span><strong>{formatNumber(data.pdf_downloads)}</strong> PDFs</span>
        <span><strong>{formatNumber(data.portal_sessions)}</strong> portal sessions</span>
        <span><strong>{rpmText}</strong> local RPM guard</span>
      </div>
      <div className="usage-links">
        {links.ai_studio_rate_limits && <a href={links.ai_studio_rate_limits} target="_blank" rel="noreferrer"><ExternalLink size={15} /> AI Studio limits</a>}
        {links.ai_studio_usage && <a href={links.ai_studio_usage} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Usage</a>}
        {links.ai_studio_spend && <a href={links.ai_studio_spend} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Spend</a>}
      </div>
    </div>
  );
}

function App() {
  const [selectedForm, setSelectedForm] = useState("passport");
  const [files, setFiles] = useState([]);
  const [masterData, setMasterData] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [autoFields, setAutoFields] = useState({});
  const [loading, setLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalUrl, setPortalUrl] = useState("");
  const [portalResult, setPortalResult] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [usage, setUsage] = useState(null);
  const [geminiKey, setGeminiKey] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [passportReference, setPassportReference] = useState("");
  const [portalProfile, setPortalProfile] = useState("portal-default");
  const uploadRef = useRef(null);

  const activeForm = formTypes.find((form) => form.id === selectedForm) || formTypes[0];
  const fields = formConfigs[activeForm.id];
  const sheet = sheetTemplates[activeForm.id];
  const completed = fields.filter((field) => String(formValues[field] || "").trim()).length;
  const completion = fields.length ? Math.round((completed / fields.length) * 100) : 0;
  const missing = fields.length - completed;
  const detectedLabel = masterData?.id_type === "NID" ? "NID card detected" : masterData?.id_type === "SAMPLE" ? "Sample profile loaded" : "Citizenship card detected";
  const fillSource = sourceText(masterData?.id_type);
  const firstFile = files[0] || null;
  const isPdf = firstFile?.type === "application/pdf" || firstFile?.name?.toLowerCase().endsWith(".pdf");
  const previewUrl = useMemo(() => (firstFile && !isPdf ? URL.createObjectURL(firstFile) : ""), [firstFile, isPdf]);
  const fileSummary = files.length
    ? `${files.length} file${files.length === 1 ? "" : "s"} selected`
    : "Upload passport source photos or PDFs";
  const portalOptions = portalGuides[selectedForm] || [];
  const portalSearch = portalSearches[selectedForm];

  useEffect(() => {
    refreshHealth();
    refreshUsage();
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function refreshHealth() {
    return fetch(`${API_BASE}/api/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }

  function refreshUsage() {
    return fetch(`${API_BASE}/api/usage`)
      .then((response) => response.json())
      .then(setUsage)
      .catch(() => setUsage(null));
  }

  async function saveGeminiKey() {
    setSettingsSaving(true);
    setSettingsMessage("");
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/settings/gemini`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: geminiKey, model: "gemini-3.5-flash" })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not save Gemini key");
      setGeminiKey("");
      setSettingsMessage("Gemini scan is ready for image and scanned PDF extraction.");
      await refreshHealth();
      await refreshUsage();
    } catch (err) {
      setError(err.message);
    } finally {
      setSettingsSaving(false);
    }
  }

  async function uploadAndExtract() {
    if (!selectedForm || files.length === 0) return;
    setLoading(true);
    setError("");
    setPortalResult("");
    const body = new FormData();
    files.forEach((selectedFile) => body.append("files", selectedFile));
    body.append("form_type", selectedForm);
    try {
      const response = await fetch(`${API_BASE}/api/extract`, { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Extraction failed");
      const { initialValues, sourceMap } = applyMasterToForm(selectedForm, payload.master_data);
      setMasterData(payload.master_data);
      setFormValues(initialValues);
      setAutoFields(sourceMap);
      await refreshUsage();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function useSampleProfile() {
    const master = { ...sampleMaster, id_type: "SAMPLE" };
    const { initialValues, sourceMap } = applyMasterToForm(selectedForm, master);
    setMasterData(master);
    setFormValues(initialValues);
    setAutoFields(sourceMap);
    setError("");
    setPortalResult("");
  }

  async function downloadPdf(printAfter = false) {
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          form_type: selectedForm,
          id_type: masterData?.id_type,
          values: formValues
        })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not generate PDF");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      if (printAfter) {
        const win = window.open(url, "_blank");
        win?.addEventListener("load", () => win.print());
      } else {
        const link = document.createElement("a");
        link.href = url;
        link.download = `${selectedForm}-filled-form.pdf`;
        link.click();
      }
      await refreshUsage();
    } catch (err) {
      setError(err.message);
    }
  }

  async function autofillPortal(urlOverride = null) {
    const targetUrl = urlOverride || portalUrl;
    if (!targetUrl) return;
    if (urlOverride) setPortalUrl(urlOverride);
    setError("");
    setPortalResult("");
    setPortalLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/portal/autofill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          portal_url: targetUrl,
          wait_for_form: true,
          wait_timeout_ms: 300000,
          browser_profile: portalProfile,
          values: {
            ...formValues,
            ...(selectedForm === "passport" && passportReference.trim()
              ? { passport_reference: passportReference.trim(), application_reference: passportReference.trim() }
              : {})
          }
        })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Portal autofill failed");
      setPortalResult(payload.message || "Your supported default browser opened. Complete login/CAPTCHA/OTP manually if needed. Autofill will watch for form pages and fill safe visible fields as they appear.");
      await refreshUsage();
    } catch (err) {
      setError(err.message);
    } finally {
      setPortalLoading(false);
    }
  }

  function usePortalUrl(url) {
    setPortalUrl(url);
    setPortalResult("");
    setError("");
  }

  function openPortalUrl(url) {
    usePortalUrl(url);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function openAndAutofillPortal(url) {
    autofillPortal(url);
  }

  function openPortalSearch() {
    if (!portalSearch) return;
    window.open(`https://www.google.com/search?q=${encodeURIComponent(portalSearch)}`, "_blank", "noopener,noreferrer");
  }

  function chooseForm(formId) {
    setSelectedForm(formId);
    setFiles([]);
    setMasterData(null);
    setFormValues({});
    setAutoFields({});
    setPortalUrl("");
    setPortalResult("");
    setPassportReference("");
    setError("");
  }

  return (
    <main className="app">
      <header className="topbar">
        <button className="brand" onClick={() => chooseForm("passport")}>
          <span className="brand-mark">NP</span>
          <span>Nepal Form Autofill</span>
        </button>
        <div className="status-pills">
          <span><LockKeyhole size={16} /> In-memory files</span>
          <span><FileScan size={16} /> {health?.ocr === "gemini_passport_extraction" ? "Gemini passport scan" : "Gemini key needed"}</span>
          <span><MousePointerClick size={16} /> Portal autofill</span>
        </div>
      </header>

      <section className="workspace">
        <aside className="control-rail">
          <div className="rail-heading">
            <p>Passport flow</p>
            <strong>Local v1</strong>
          </div>
          <div className="form-list">
            {formTypes.map((form) => {
              const Icon = form.icon;
              return (
                <button
                  className={`form-choice ${selectedForm === form.id ? "active" : ""}`}
                  data-accent={form.accent}
                  key={form.id}
                  onClick={() => chooseForm(form.id)}
                >
                  <Icon size={20} />
                  <span>
                    <strong>{form.title}</strong>
                    <small>{form.nepali}</small>
                  </span>
                </button>
              );
            })}
          </div>
          <div className="privacy-note">
            <ShieldCheck size={20} />
            <span>Uploads are processed by the backend and are not saved by the app.</span>
          </div>
        </aside>

        <section className="main-panel">
          <div className="hero-band">
            <div>
              <span className="eyebrow"><Sparkles size={16} /> Passport assistant</span>
              <h1>Upload passport documents. Review once. Fill ePassport locally.</h1>
              <p>Send citizenship, NID, previous passport, or supporting PDFs/photos to Gemini, then review the extracted passport fields before opening the Nepal ePassport portal.</p>
            </div>
            <div className="flow-card">
              <div className={masterData ? "done" : "current"}><FileScan size={19} /> Scan documents</div>
              <div className={masterData ? "current" : ""}><ClipboardCheck size={19} /> Review fields</div>
              <div><Download size={19} /> PDF / Portal</div>
            </div>
          </div>

          {!masterData && (
            <div className="intake-grid">
              <div className="upload-panel">
                <button className="back-button" onClick={() => uploadRef.current?.click()}>
                  <ChevronLeft size={16} /> Select files
                </button>
                <div className="section-title">
                  <h2>{activeForm.title}</h2>
                  <p>{activeForm.nepali}</p>
                </div>
                <input
                  ref={uploadRef}
                  type="file"
                  accept="image/*,.pdf,application/pdf"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files || []))}
                  hidden
                />
                <button className="dropzone" onClick={() => uploadRef.current?.click()}>
                  {previewUrl ? <img src={previewUrl} alt="Selected ID preview" /> : isPdf ? <FileText size={46} /> : <Upload size={44} />}
                  <span>{fileSummary}</span>
                  <small>{files.length ? files.map((selectedFile) => selectedFile.name).join(", ") : "JPG, PNG, camera photo, searchable PDF, or scanned PDF"}</small>
                </button>
                <div className="button-row">
                  <button className="primary" disabled={files.length === 0 || loading} onClick={uploadAndExtract}>
                    {loading ? <Loader2 className="spin" size={18} /> : <IdCard size={18} />}
                    Extract and fill
                  </button>
                  <button className="secondary" onClick={useSampleProfile}>
                    <Sparkles size={18} />
                    Try sample
                  </button>
                </div>
                {error && <p className="error">{error}</p>}
              </div>

          <div className="reference-panel">
                <h3>What it fills automatically</h3>
                {health?.ocr !== "gemini_passport_extraction" && (
                  <div className="key-panel">
                    <h4>Enable Gemini passport scanning</h4>
                    <p>Paste a Gemini API key once. Gemini reads the uploaded passport source packet and extracts names, dates, ID numbers, family details, and contact fields.</p>
                    <div className="key-row">
                      <input
                        type="password"
                        value={geminiKey}
                        onChange={(event) => setGeminiKey(event.target.value)}
                        placeholder="AIza..."
                      />
                      <button className="secondary" disabled={!geminiKey || settingsSaving} onClick={saveGeminiKey}>
                        {settingsSaving ? <Loader2 className="spin" size={17} /> : <ShieldCheck size={17} />}
                        Save key
                      </button>
                    </div>
                    {settingsMessage && <small>{settingsMessage}</small>}
                  </div>
                )}
                <div className="mini-fields">
                  {fields.slice(0, 10).map((field) => {
                    const label = fieldLabels[field] || [field, field];
                    return <span key={field}>{label[0]}</span>;
                  })}
                </div>
                <div className="reference-steps">
                  <p><BadgeCheck size={18} /> Passport source details become one reviewed application profile.</p>
                  <p><BadgeCheck size={18} /> Green fields came from the ID; yellow fields still need review.</p>
                  <p><BadgeCheck size={18} /> Portal autofill never presses final submit.</p>
                </div>
                <UsagePanel usage={usage} onRefresh={refreshUsage} />
              </div>
            </div>
          )}

          {masterData && (
            <div className="review-layout">
              <aside className="profile-card">
                <div className="detected"><Check size={18} /> {detectedLabel}</div>
                <h3>{masterData.full_name_english || "Extracted profile"}</h3>
                <p>{masterData.full_name_nepali || "Review the extracted data before using it."}</p>
                <dl>
                  <div><dt>ID</dt><dd>{masterData.citizenship_number || masterData.nid_number || "Missing"}</dd></div>
                  <div><dt>District</dt><dd>{masterData.permanent_address?.district || "Missing"}</dd></div>
                  <div><dt>DOB</dt><dd>{masterData.date_of_birth || "Missing"}</dd></div>
                </dl>
                <div className="completion-box">
                  <span>{completion}% complete</span>
                  <div className="progress"><i style={{ width: `${completion}%` }} /></div>
                  <small>{missing ? `${missing} fields need a value` : "Ready to download or fill a portal"}</small>
                </div>
                <UsagePanel usage={usage} onRefresh={refreshUsage} />
                <button className="secondary full" onClick={() => setMasterData(null)}>Upload another packet</button>
              </aside>

              <section className="form-board">
                <div className="board-head">
                  <div>
                    <p className="office-line">{sheet.office}</p>
                    <h2>{sheet.title}</h2>
                    <span>{sheet.note}</span>
                  </div>
                  <div className="photo-box">Photo<br />फोटो</div>
                </div>

                {sheet.sections.map(([sectionTitle, sectionFields]) => (
                  <section className="sheet-section" key={sectionTitle}>
                    <h3>{sectionTitle}</h3>
                    <div className="sheet-table">
                      {sectionFields.map((field) => {
                        const label = fieldLabels[field] || [field, field];
                        const filled = String(formValues[field] || "").trim();
                        const auto = autoFields[field];
                        return (
                          <label className={`sheet-cell ${filled ? "filled" : "empty"}`} key={field}>
                            <span className="label-line">{label[0]} <em>{label[1]}</em></span>
                            <input
                              value={formValues[field] || ""}
                              onChange={(event) => {
                                const value = event.target.value;
                                setFormValues((current) => ({ ...current, [field]: value }));
                                setAutoFields((current) => ({ ...current, [field]: current[field] && Boolean(value) }));
                              }}
                            />
                            <small>{auto ? fillSource : "Please fill manually"}</small>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                ))}

                <div className="sheet-signatures">
                  <span>Applicant signature / आवेदकको हस्ताक्षर</span>
                  <span>Right thumb / दायाँ औंठाछाप</span>
                  <span>Office use only / कार्यालय प्रयोजन</span>
                </div>

                <div className="actions">
                  <button className="primary" onClick={() => downloadPdf(false)}><Download size={18} /> Download PDF</button>
                  <button className="secondary" onClick={() => downloadPdf(true)}><Printer size={18} /> Print</button>
                </div>

                <div className="portal-panel">
                  <div>
                    <h3>Fill an online portal</h3>
                    <p>Select a portal and start autofill. The app opens the selected portal profile, waits while you manually finish CAPTCHA/login/location, then fills matching safe fields when the real form appears.</p>
                  </div>
                  <div className="portal-profile-row">
                    <label>
                      <span>Portal browser account</span>
                      <select value={portalProfile} onChange={(event) => setPortalProfile(event.target.value)}>
                        <option value="portal-default">Default portal profile</option>
                        <option value="portal-account-2">Second account profile</option>
                        <option value="portal-account-3">Third account profile</option>
                      </select>
                    </label>
                    <small>Each profile keeps its own browser cookies. Use this when different users or accounts need separate portal login sessions.</small>
                  </div>
                  {selectedForm === "bank_account" ? (
                    <div className="portal-later">
                      <strong>Bank portals vary by bank.</strong>
                      <span>We will handle bank account portals later with bank-specific field maps.</span>
                    </div>
                  ) : (
                    <div className="portal-directory">
                      {selectedForm === "passport" && (
                        <div className="passport-help">
                          <div>
                            <strong>e-Passport workflow</strong>
                            <span>New application: open the Online Pre-Enrollment Form, fill it, submit it yourself, then keep the PDF receipt or appointment slip.</span>
                          </div>
                          <div>
                            <strong>Already applied?</strong>
                            <span>Use Passport Status Check. The Application ID / reference number is usually in SMS, email, downloaded PDF, appointment slip, payment receipt, or inside the application portal.</span>
                          </div>
                          <label>
                            <span>Application ID / Reference Number</span>
                            <input
                              value={passportReference}
                              onChange={(event) => setPassportReference(event.target.value)}
                              placeholder="Example: NEP123456789"
                            />
                          </label>
                        </div>
                      )}
                      <div className="portal-directory-head">
                        <strong>Pick the portal instead of searching manually</strong>
                        <button className="link-button" onClick={openPortalSearch}>Search official links</button>
                      </div>
                      {portalOptions.map((portal) => (
                        <div className="portal-option" key={`${portal.title}-${portal.url}`}>
                          <div>
                            <strong>{portal.title}</strong>
                            <code>{portal.url}</code>
                            <span>{portal.note}</span>
                          </div>
                          <div className="portal-option-actions">
                            <button className="primary portal-primary" disabled={portalLoading} onClick={() => openAndAutofillPortal(portal.url)}>
                              {portalLoading ? <Loader2 className="spin" size={16} /> : <MousePointerClick size={16} />}
                              Open & Autofill
                            </button>
                            <button className="secondary" onClick={() => openPortalUrl(portal.url)}>Open</button>
                            <button className="secondary" onClick={() => usePortalUrl(portal.url)}>Use URL</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="portal-row">
                    <input
                      value={portalUrl}
                      onChange={(event) => setPortalUrl(event.target.value)}
                      placeholder="https://example.gov.np/application"
                    />
                    <button className="secondary" disabled={!portalUrl || portalLoading} onClick={autofillPortal}>
                      {portalLoading ? <Loader2 className="spin" size={18} /> : <MousePointerClick size={18} />}
                      Autofill portal
                    </button>
                  </div>
                  <small>Log in or pass CAPTCHA/OTP manually if the portal asks. Autofill watches up to 5 minutes across multi-page forms and fills the real form page automatically when it appears. Password, CAPTCHA, OTP, payment, and final submit are never filled or clicked automatically. Supported default browsers: Chrome, Edge, or Brave.</small>
                  {portalResult && <p className="success">{portalResult}</p>}
                </div>
                {error && <p className="error">{error}</p>}
              </section>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
