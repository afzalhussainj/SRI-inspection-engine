import { useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { resolveMediaUrl } from "./api";
import { DEFAULT_BRANDING } from "./brandingDefaults";
import { FormPage } from "./FormPage";

const UI_TEXT: Record<string, Record<string, string>> = {
  en: {
    openInspection: "Open your inspection",
    enterIds:
      "Paste the inspection_instance_id and your recipient uuid from the link you received.",
    inspectionInstanceId: "Inspection Instance ID",
    recipientUuid: "Recipient UUID",
    openForm: "Open form",
    linkFormat: "Link format"
  },
  es: {
    openInspection: "Abrir inspección",
    enterIds:
      "Pegue el inspection_instance_id y el uuid del destinatario desde el enlace recibido.",
    inspectionInstanceId: "ID de instancia de inspección",
    recipientUuid: "UUID del destinatario",
    openForm: "Abrir formulario",
    linkFormat: "Formato de enlace"
  }
};

function t(lang: string, key: string): string {
  return UI_TEXT[lang]?.[key] ?? UI_TEXT.en[key] ?? key;
}

function Home() {
  const nav = useNavigate();
  const [inspectionId, setInspectionId] = useState("");
  const [uuid, setUuid] = useState("");
  const locale = "en";
  const branding = DEFAULT_BRANDING;
  const logoSrc = resolveMediaUrl(branding.logo_url);

  function go() {
    const a = inspectionId.trim();
    const b = uuid.trim();
    if (!a || !b) return;
    nav(`/${a}/${b}`);
  }

  return (
    <div className="container">
      <div className="hero">
        <div className="brandBlock">
          {logoSrc ? <img src={logoSrc} alt={`${branding.hospital_program_name} logo`} className="brandLogo" /> : null}
          <div>
            <div className="badge" style={{ borderColor: `${branding.primary_color}66`, color: branding.primary_color }}>
              {branding.hospital_program_name}
            </div>
            {branding.tagline ? <div className="muted small">{branding.tagline}</div> : null}
          </div>
        </div>
        <h1>{t(locale, "openInspection")}</h1>
        <p className="muted">{t(locale, "enterIds")}</p>

        <div className="card">
          <div className="grid2">
            <div className="field">
              <label htmlFor="inspection_id">{t(locale, "inspectionInstanceId")}</label>
              <input
                id="inspection_id"
                className="textControl"
                placeholder="e.g. 8b6f7c2e-1b2c-4b67-ae3b-6e52b30f4b6a"
                value={inspectionId}
                onChange={(e) => setInspectionId(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="recipient_uuid">{t(locale, "recipientUuid")}</label>
              <input
                id="recipient_uuid"
                className="textControl"
                placeholder="e.g. 7a9c5c7f-0e6a-4d2a-9a52-3e58d4e9d85b"
                value={uuid}
                onChange={(e) => setUuid(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") go();
                }}
              />
            </div>
          </div>

          <div className="actions">
            <button type="button" className="buttonPrimary" onClick={go} disabled={!inspectionId.trim() || !uuid.trim()}>
              {t(locale, "openForm")}
            </button>
          </div>

          <div className="muted small">
            {t(locale, "linkFormat")}: <span className="mono">/{`{inspection_instance_id}`}/{`{uuid}`}</span>
          </div>
        </div>
        {branding.footer_text ? <div className="muted small brandFooter">{branding.footer_text}</div> : null}
      </div>
    </div>
  );
}

export function App() {
  return (
    <>
      <a className="skipLink" href="#main-content">
        Skip to main content
      </a>
      <div id="main-content" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/:inspectionId/:uuid" element={<FormPage />} />
        </Routes>
      </div>
    </>
  );
}
