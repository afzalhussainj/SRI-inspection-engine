import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSubmissionPdf, getForm, resolveMediaUrl, submitForm } from "./api";
import { DEFAULT_BRANDING } from "./brandingDefaults";
import type { FieldSchema, GetFormResponse } from "./types";

const LANGUAGE_DISPLAY: Record<string, string> = {
  en: "English",
  es: "Spanish"
};

function languageLabel(code: string): string {
  if (LANGUAGE_DISPLAY[code]) return LANGUAGE_DISPLAY[code];
  if (/^[a-z]{2}(-[A-Z]{2})?$/.test(code)) {
    return code.length === 2 ? code.toUpperCase() : code;
  }
  return code;
}

function formatReferenceId(id: string | undefined): string {
  if (!id) return "—";
  if (id.length <= 18) return id;
  return `${id.slice(0, 6)}…${id.slice(-4)}`;
}

const UI_TEXT: Record<string, Record<string, string>> = {
  en: {
    error: "Error",
    success: "Success",
    inspectionForm: "Inspection questionnaire",
    loading: "Loading…",
    formLanguage: "Form language",
    outputLanguage: "Output language",
    formLanguageHint: "Updates the questionnaire text shown below (questions and section titles).",
    outputLanguageHint: "Sets the language for your Structured Wellbeing Risk Summary.",
    questionnaireIntroLine1:
      "This structured questionnaire reviews how household caregiving routines and decision processes are organized during early transition periods.",
    questionnaireIntroLine2:
      "It focuses on structure, clarity, and coordination — not parenting quality or medical conditions.",
    questionnaireIntroLine3:
      "Responses are confidential and anonymous unless otherwise configured by your institution.",
    questionnaireIntroLine4:
      "This questionnaire does not assess safety compliance, medical risk, or probability of harm.",
    submit: "Submit",
    submitting: "Submitting…",
    submittedToast: "Submitted successfully.",
    loadFailed: "Failed to load form",
    submitFailed: "Failed to submit",
    downloadPdf: "Download PDF summary",
    downloadingPdf: "Preparing PDF…",
    downloadPdfFailed: "Could not download the PDF.",
    updatingQuestionnaire: "Updating questionnaire…",
    referenceDetails: "Reference details",
    referenceDetailsHint: "For support requests only — not required to complete the questionnaire.",
    referenceInspection: "Inspection reference",
    referenceLink: "Link reference",
    referenceFormVersion: "Form version",
    submissionReceivedTitle: "Submission received",
    priorLinkCompletedBody:
      "Thank you. This inspection link has already been completed, so no further action is needed.",
    justRecordedBody: "Thank you. Your responses have been recorded.",
    justRecordedFollowUp:
      "Your institution will use this information according to its own processes. If you were offered a summary document, you may download it below when available.",
    pdfNotAvailableNote:
      "Summaries for this program are provided through your care team or program portal. If you need a copy, please contact your coordinator.",
    submittedThanks: "Thank you for completing this structured review."
  },
  es: {
    error: "Error",
    success: "Éxito",
    inspectionForm: "Cuestionario de inspección",
    loading: "Cargando…",
    formLanguage: "Idioma del formulario",
    outputLanguage: "Idioma de salida",
    formLanguageHint: "Actualiza el texto del cuestionario que se muestra a continuacion (preguntas y titulos de seccion).",
    outputLanguageHint: "Define el idioma de su Resumen de Riesgo de Bienestar Estructurado.",
    questionnaireIntroLine1:
      "Este cuestionario estructurado revisa como se organizan las rutinas de cuidado del hogar y los procesos de decision durante periodos tempranos de transicion.",
    questionnaireIntroLine2:
      "Se enfoca en estructura, claridad y coordinacion, no en calidad de crianza ni en condiciones medicas.",
    questionnaireIntroLine3:
      "Las respuestas son confidenciales y anonimas, salvo que su institucion configure lo contrario.",
    questionnaireIntroLine4:
      "Este cuestionario no evalua cumplimiento de seguridad, riesgo medico ni probabilidad de dano.",
    submit: "Enviar",
    submitting: "Enviando…",
    submittedToast: "Enviado correctamente.",
    loadFailed: "Error al cargar el formulario",
    submitFailed: "Error al enviar",
    downloadPdf: "Descargar resumen en PDF",
    downloadingPdf: "Preparando PDF…",
    downloadPdfFailed: "No se pudo descargar el PDF.",
    updatingQuestionnaire: "Actualizando cuestionario…",
    referenceDetails: "Detalles de referencia",
    referenceDetailsHint: "Solo para solicitudes de soporte; no es necesario para completar el cuestionario.",
    referenceInspection: "Referencia de inspección",
    referenceLink: "Referencia del enlace",
    referenceFormVersion: "Versión del formulario",
    submissionReceivedTitle: "Recepción registrada",
    priorLinkCompletedBody:
      "Gracias. Este enlace de inspección ya fue completado; no se requiere ninguna acción adicional.",
    justRecordedBody: "Gracias. Sus respuestas han sido registradas.",
    justRecordedFollowUp:
      "Su institución utilizará esta información según sus propios procesos. Si se le ofreció un documento de resumen, podrá descargarlo a continuación cuando esté disponible.",
    pdfNotAvailableNote:
      "Los resumenes de este programa se proporcionan a través de su equipo de atención o el portal del programa. Si necesita una copia, comuníquese con su coordinador.",
    submittedThanks: "Gracias por completar esta revision estructurada."
  }
};

function t(lang: string, key: string): string {
  return UI_TEXT[lang]?.[key] ?? UI_TEXT.en[key] ?? key;
}

function Toast({
  message,
  kind,
  onClose,
  locale
}: {
  message: string;
  kind: "error" | "success";
  onClose: () => void;
  locale: string;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, 4500);
    return () => window.clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={`toast ${kind}`}>
      <div className="toastTitle">{kind === "error" ? t(locale, "error") : t(locale, "success")}</div>
      <div className="toastMsg">{message}</div>
      <button className="toastX" onClick={onClose} aria-label="Close">
        ×
      </button>
    </div>
  );
}

function Field({
  field,
  value,
  onChange
}: {
  field: FieldSchema;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const id = `field_${field.id}`;
  const common = {
    id,
    name: field.id
  };

  if (field.type === "number") {
    return (
      <div className="field">
        <label htmlFor={id}>
          {field.label} {field.required ? <span className="req">*</span> : null}
        </label>
        {field.help_text ? <div className="muted small">{field.help_text}</div> : null}
        <input
          {...common}
          className="textControl"
          type="number"
          value={value === "" ? "" : typeof value === "number" ? value : ""}
          onChange={(e) => {
            const v = e.target.value;
            onChange(v === "" ? "" : Number(v));
          }}
          required={field.required}
        />
      </div>
    );
  }

  if (field.type === "select") {
    const opts = Array.isArray(field.options) ? field.options : [];
    return (
      <div className="field">
        <label htmlFor={id}>
          {field.label} {field.required ? <span className="req">*</span> : null}
        </label>
        {field.help_text ? <div className="muted small">{field.help_text}</div> : null}
        <select
          {...common}
          className="selectControl"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
          required={field.required}
        >
          {field.required ? null : <option value="">—</option>}
          {opts.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="field">
      <label htmlFor={id}>
        {field.label} {field.required ? <span className="req">*</span> : null}
      </label>
      {field.help_text ? <div className="muted small">{field.help_text}</div> : null}
      <input
        {...common}
        className="textControl"
        type="text"
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(e.target.value)}
        required={field.required}
      />
    </div>
  );
}

export function FormPage() {
  const { inspectionId, uuid } = useParams();
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ kind: "error" | "success"; message: string } | null>(null);
  const [data, setData] = useState<GetFormResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [outputLanguage, setOutputLanguage] = useState<string | null>(null);
  const [formLanguage, setFormLanguage] = useState<string>("en");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [logoBroken, setLogoBroken] = useState(false);
  const linkSyncKeyRef = useRef<string>("");

  const ids = useMemo(() => {
    if (!inspectionId || !uuid) return null;
    return { inspectionId, uuid };
  }, [inspectionId, uuid]);

  const locale = formLanguage || "en";
  const branding = data?.branding ?? DEFAULT_BRANDING;
  const brandColor = branding.primary_color || "#1F2937";
  const logoSrc = resolveMediaUrl(branding.logo_url);
  const languageCodes = data?.output_languages?.length ? data.output_languages : [];
  const outputSelectValue =
    outputLanguage ?? data?.default_output_language ?? languageCodes[0] ?? "";
  const completionKnown = submitted || (data?.already_submitted ?? false);
  const orgPresent = Boolean((branding.organization_id ?? "").trim());
  const pdfAvailable = completionKnown && ids != null && !orgPresent;
  const showInteractiveForm = Boolean(data && !data.already_submitted && !submitted);
  const isPriorCompletedOnly = Boolean(completionKnown && data?.already_submitted && !submitted);
  const isFreshSubmit = Boolean(submitted);

  useEffect(() => {
    setLogoBroken(false);
  }, [branding.logo_url]);

  useEffect(() => {
    setSubmitted(false);
  }, [ids?.inspectionId, ids?.uuid]);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!ids) return;
      setLoading(true);
      setToast(null);
      try {
        const res = await getForm(ids.inspectionId, ids.uuid, formLanguage);
        if (cancelled) return;
        setData(res);
        const effectiveFormLang = res.selected_content_language ?? formLanguage ?? res.default_output_language ?? "en";
        setFormLanguage(effectiveFormLang);

        const lk = `${ids.inspectionId}:${ids.uuid}`;
        if (linkSyncKeyRef.current !== lk) {
          linkSyncKeyRef.current = lk;
          setOutputLanguage(res.default_output_language ?? (res.output_languages?.[0] ?? null));
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setData(null);
        const msg = e instanceof Error ? e.message : t(locale, "loadFailed");
        setToast({ kind: "error", message: msg });
      } finally {
        if (cancelled) return;
        setLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [ids, formLanguage]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ids || !data) return;
    setSubmitting(true);
    setToast(null);
    try {
      await submitForm(ids.inspectionId, ids.uuid, answers, outputSelectValue || undefined);
      setSubmitted(true);
      setToast({ kind: "success", message: t(locale, "submittedToast") });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t(locale, "submitFailed");
      setToast({ kind: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  }

  async function onDownloadPdf() {
    if (!ids) return;
    setPdfDownloading(true);
    setToast(null);
    try {
      const blob = await fetchSubmissionPdf(ids.inspectionId, ids.uuid);
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = "StructuredWellbeingRiskSummary.pdf";
      a.rel = "noopener";
      a.click();
      URL.revokeObjectURL(objectUrl);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : t(locale, "downloadPdfFailed");
      setToast({ kind: "error", message: message || t(locale, "downloadPdfFailed") });
    } finally {
      setPdfDownloading(false);
    }
  }

  return (
    <div className="container">
      {toast ? <Toast kind={toast.kind} message={toast.message} onClose={() => setToast(null)} locale={locale} /> : null}
      <header className="pageHeader pageHeaderStacked">
        <div className="pageHeaderMain">
          <div className="brandBlock brandBlockHero">
            {logoSrc && !logoBroken ? (
              <img
                src={logoSrc}
                alt={`${branding.hospital_program_name} logo`}
                className="brandLogo"
                loading="eager"
                decoding="async"
                onError={() => setLogoBroken(true)}
              />
            ) : null}
            <div className="brandText">
              <h1 className="programTitle" style={{ color: brandColor }}>
                {branding.hospital_program_name}
              </h1>
              {branding.tagline ? <p className="programTagline">{branding.tagline}</p> : null}
            </div>
          </div>
          <p className="formPageSubtitle">{t(locale, "inspectionForm")}</p>
        </div>
      </header>

      {loading && !data ? <div className="card cardLoading">{t(locale, "loading")}</div> : null}

      {completionKnown && data ? (
        <section className="card completionCard" aria-labelledby="completion-heading">
          <h2 id="completion-heading" className="completionTitle">
            {t(locale, "submissionReceivedTitle")}
          </h2>
          <p className="completionLead">
            {isPriorCompletedOnly ? t(locale, "priorLinkCompletedBody") : t(locale, "justRecordedBody")}
          </p>
          {isFreshSubmit ? (
            <>
              <p className="muted completionSecondary">{t(locale, "submittedThanks")}</p>
              <p className="muted small">{t(locale, "justRecordedFollowUp")}</p>
            </>
          ) : null}
          {pdfAvailable ? (
            <div className="completionActions">
              <button type="button" className="buttonPrimary" onClick={onDownloadPdf} disabled={pdfDownloading}>
                {pdfDownloading ? t(locale, "downloadingPdf") : t(locale, "downloadPdf")}
              </button>
            </div>
          ) : completionKnown && orgPresent ? (
            <p className="muted small completionNote" role="note">
              {t(locale, "pdfNotAvailableNote")}
            </p>
          ) : null}
        </section>
      ) : null}

      {showInteractiveForm && data ? (
        <form
          onSubmit={onSubmit}
          className={`card formCard${loading && data ? " formCardRefreshing" : ""}`}
          aria-busy={loading && !!data}
        >
          {loading && data ? (
            <div className="formRefreshBanner" role="status">
              {t(locale, "updatingQuestionnaire")}
            </div>
          ) : null}

          <div className="formCardHead">
            <h2 className="schemaTitle">{data.schema.title}</h2>
          </div>

          <div className="introBlock">
            <p>{t(locale, "questionnaireIntroLine1")}</p>
            <p>{t(locale, "questionnaireIntroLine2")}</p>
            <p>{t(locale, "questionnaireIntroLine3")}</p>
            <p>{t(locale, "questionnaireIntroLine4")}</p>
          </div>

          {languageCodes.length > 0 ? (
            <div className="langRow">
              <div className="field fieldLang">
                <label htmlFor="form_language">{t(locale, "formLanguage")}</label>
                <select
                  id="form_language"
                  className="selectControl"
                  value={formLanguage}
                  onChange={(e) => setFormLanguage(e.target.value || (data.default_output_language ?? "en"))}
                  disabled={submitting}
                >
                  {languageCodes.map((lang) => (
                    <option key={lang} value={lang}>
                      {languageLabel(lang)}
                    </option>
                  ))}
                </select>
                <span className="fieldHint">{t(locale, "formLanguageHint")}</span>
              </div>
              <div className="field fieldLang">
                <label htmlFor="output_language">{t(locale, "outputLanguage")}</label>
                <select
                  id="output_language"
                  className="selectControl"
                  value={outputSelectValue}
                  onChange={(e) => setOutputLanguage(e.target.value || null)}
                  disabled={submitting}
                >
                  {languageCodes.map((lang) => (
                    <option key={`out-${lang}`} value={lang}>
                      {languageLabel(lang)}
                    </option>
                  ))}
                </select>
                <span className="fieldHint">{t(locale, "outputLanguageHint")}</span>
              </div>
            </div>
          ) : null}

          {data.schema.sections.map((s) => (
            <div key={s.id} className="section">
              <h3 className="sectionTitle">{s.title}</h3>
              {s.fields.map((f) => (
                <Field
                  key={f.id}
                  field={f}
                  value={answers[f.id]}
                  onChange={(next) => setAnswers((prev) => ({ ...prev, [f.id]: next }))}
                />
              ))}
            </div>
          ))}

          <div className="actions">
            <button type="submit" className="buttonPrimary" disabled={submitting}>
              {submitting ? t(locale, "submitting") : t(locale, "submit")}
            </button>
          </div>
        </form>
      ) : null}

      {data ? (
        <details className="referenceDetails">
          <summary className="referenceSummary">{t(locale, "referenceDetails")}</summary>
          <p className="muted small referenceDetailsHint">{t(locale, "referenceDetailsHint")}</p>
          <div className="referencePanel" role="group" aria-label={t(locale, "referenceDetails")}>
            <div className="referenceRow">
              <span className="referenceLabel">{t(locale, "referenceInspection")}</span>
              <code className="referenceValue" title={inspectionId}>
                {formatReferenceId(inspectionId)}
              </code>
            </div>
            <div className="referenceRow">
              <span className="referenceLabel">{t(locale, "referenceLink")}</span>
              <code className="referenceValue" title={uuid}>
                {formatReferenceId(uuid)}
              </code>
            </div>
            <div className="referenceRow">
              <span className="referenceLabel">{t(locale, "referenceFormVersion")}</span>
              <code className="referenceValue mono" title={data.config_version_id}>
                {formatReferenceId(data.config_version_id)}
              </code>
            </div>
          </div>
        </details>
      ) : null}

      {branding.footer_text ? <div className="muted small brandFooter">{branding.footer_text}</div> : null}
    </div>
  );
}
