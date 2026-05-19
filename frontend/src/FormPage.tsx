import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiHttpError, fetchSubmissionPdf, getForm, isApiHttpError, resolveMediaUrl, submitForm } from "./api";
import { Alert } from "./components/Alert";
import { Button } from "./components/Button";
import { FieldError } from "./components/FieldError";
import { LoadingState } from "./components/LoadingState";
import { NumberInput } from "./components/NumberInput";
import { SelectField } from "./components/SelectField";
import { TextInput } from "./components/TextInput";
import { DEFAULT_BRANDING } from "./brandingDefaults";
import { scrubAnswersForSubmit, validateAnswersForSubmit } from "./form/clientValidate";
import { buildInitialAnswers } from "./form/initialAnswers";
import { mapServerValidationToFieldErrors } from "./form/mapServerValidationToFieldErrors";
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
    inspectionForm: "Inspection questionnaire",
    loading: "Loading questionnaire…",
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
    loadFailed: "Could not load questionnaire",
    submitFailed: "Could not submit responses",
    downloadPdf: "Download PDF summary",
    downloadingPdf: "Preparing PDF…",
    downloadPdfFailed: "Could not download the PDF.",
    updatingQuestionnaire: "Updating questionnaire…",
    referenceDetails: "Submission Reference",
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
    submittedThanks: "Thank you for completing this structured review.",
    selectPlaceholder: "Select an option",
    selectPlaceholderOptional: "Optional — select an option",
    validationSummaryTitle: "Please review the items below before continuing.",
    networkTitle: "Connection problem",
    networkError: "We couldn’t reach the server. Check your internet connection and try again.",
    serverErrorTitle: "Something went wrong",
    serverError: "Please wait a moment and try again. If the problem continues, contact your coordinator.",
    genericLoadError: "The questionnaire could not be loaded.",
    expiredTitle: "This link has expired",
    expiredBody: "If you still need to respond, contact your coordinator for a new invitation.",
    notFoundTitle: "We couldn’t open this link",
    notFoundBody: "Check that the address matches your invitation, or ask your coordinator to resend the link.",
    unavailableTitle: "This questionnaire isn’t available",
    unavailableBody: "It may not be published yet. Please try again later or contact your program administrator.",
    invalidLinkTitle: "This address doesn’t look valid",
    invalidLinkBody: "The link may be incomplete. Compare it with the invitation you received.",
    retryLoad: "Try again",
    closeToast: "Dismiss notification",
    submitErrorTitle: "We couldn’t save your responses",
    errorSelectRequired: "Please select an option to continue.",
    errorTextRequired: "Please complete this field.",
    errorNumberRequired: "Please enter a number.",
    errorNumberInvalid: "Enter a valid number.",
    errorBackendText: "Please check this text field.",
    errorBackendString: "Please check this field.",
    errorBackendOption: "Please choose one of the listed options.",
    errorBackendUnsupported: "This field could not be validated. Please review your answer.",
    errorBackendGeneral: "Please review your answers and try again."
  },
  es: {
    inspectionForm: "Cuestionario de inspección",
    loading: "Cargando cuestionario…",
    formLanguage: "Idioma del formulario",
    outputLanguage: "Idioma de salida",
    formLanguageHint: "Actualiza el texto del cuestionario que se muestra a continuación (preguntas y títulos de sección).",
    outputLanguageHint: "Define el idioma de su Resumen de Riesgo de Bienestar Estructurado.",
    questionnaireIntroLine1:
      "Este cuestionario estructurado revisa cómo se organizan las rutinas de cuidado del hogar y los procesos de decisión durante periodos tempranos de transición.",
    questionnaireIntroLine2:
      "Se enfoca en estructura, claridad y coordinación, no en calidad de crianza ni en condiciones médicas.",
    questionnaireIntroLine3:
      "Las respuestas son confidenciales y anónimas, salvo que su institución configure lo contrario.",
    questionnaireIntroLine4:
      "Este cuestionario no evalúa cumplimiento de seguridad, riesgo médico ni probabilidad de daño.",
    submit: "Enviar",
    submitting: "Enviando…",
    loadFailed: "No se pudo cargar el cuestionario",
    submitFailed: "No se pudieron enviar las respuestas",
    downloadPdf: "Descargar resumen en PDF",
    downloadingPdf: "Preparando PDF…",
    downloadPdfFailed: "No se pudo descargar el PDF.",
    updatingQuestionnaire: "Actualizando cuestionario…",
    referenceDetails: "Referencia de envío",
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
      "Los resúmenes de este programa se proporcionan a través de su equipo de atención o el portal del programa. Si necesita una copia, comuníquese con su coordinador.",
    submittedThanks: "Gracias por completar esta revisión estructurada.",
    selectPlaceholder: "Seleccione una opción",
    selectPlaceholderOptional: "Opcional — seleccione una opción",
    validationSummaryTitle: "Revise los siguientes puntos antes de continuar.",
    networkTitle: "Problema de conexión",
    networkError: "No pudimos conectar con el servidor. Compruebe su conexión e inténtelo de nuevo.",
    serverErrorTitle: "Algo salió mal",
    serverError: "Espere un momento e inténtelo de nuevo. Si el problema continúa, comuníquese con su coordinador.",
    genericLoadError: "No se pudo cargar el cuestionario.",
    expiredTitle: "Este enlace ha vencido",
    expiredBody: "Si aún necesita responder, solicite a su coordinador una nueva invitación.",
    notFoundTitle: "No pudimos abrir este enlace",
    notFoundBody: "Compruebe que la dirección coincida con su invitación o pida a su coordinador que reenvíe el enlace.",
    unavailableTitle: "Este cuestionario no está disponible",
    unavailableBody: "Es posible que aún no esté publicado. Inténtelo más tarde o contacte al administrador del programa.",
    invalidLinkTitle: "Esta dirección no parece válida",
    invalidLinkBody: "El enlace puede estar incompleto. Compárelo con la invitación que recibió.",
    retryLoad: "Intentar de nuevo",
    closeToast: "Cerrar notificación",
    submitErrorTitle: "No pudimos guardar sus respuestas",
    errorSelectRequired: "Seleccione una opción para continuar.",
    errorTextRequired: "Complete este campo.",
    errorNumberRequired: "Introduzca un número.",
    errorNumberInvalid: "Introduzca un número válido.",
    errorBackendText: "Revise este campo de texto.",
    errorBackendString: "Revise este campo.",
    errorBackendOption: "Elija una de las opciones listadas.",
    errorBackendUnsupported: "No se pudo validar este campo. Revise su respuesta.",
    errorBackendGeneral: "Revise sus respuestas e inténtelo de nuevo."
  }
};

function t(lang: string, key: string): string {
  return UI_TEXT[lang]?.[key] ?? UI_TEXT.en[key] ?? key;
}

function describeGetFormFailure(err: unknown, lang: string): { title: string; body: string } {
  if (err instanceof TypeError && err.message === "NETWORK") {
    return { title: t(lang, "networkTitle"), body: t(lang, "networkError") };
  }
  if (isApiHttpError(err)) {
    if (err.status === 410) return { title: t(lang, "expiredTitle"), body: t(lang, "expiredBody") };
    if (err.status === 404) return { title: t(lang, "notFoundTitle"), body: t(lang, "notFoundBody") };
    if (err.status === 409) return { title: t(lang, "unavailableTitle"), body: t(lang, "unavailableBody") };
    if (err.status === 400) return { title: t(lang, "invalidLinkTitle"), body: t(lang, "invalidLinkBody") };
    return { title: t(lang, "serverErrorTitle"), body: t(lang, "serverError") };
  }
  return { title: t(lang, "loadFailed"), body: t(lang, "genericLoadError") };
}

function describeSubmitFailure(err: unknown, lang: string): string {
  if (err instanceof TypeError && err.message === "NETWORK") {
    return t(lang, "networkError");
  }
  if (isApiHttpError(err)) {
    if (err.status >= 500) return t(lang, "serverError");
    if (err.status === 409) return t(lang, "priorLinkCompletedBody");
    return t(lang, "submitFailed");
  }
  return t(lang, "submitFailed");
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
    const timer = window.setTimeout(onClose, 5200);
    return () => window.clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={`toast ${kind}`} role="status">
      <div className="toastTitle">{kind === "error" ? t(locale, "submitFailed") : t(locale, "downloadPdf")}</div>
      <div className="toastMsg">{message}</div>
      <button type="button" className="toastX" onClick={onClose} aria-label={t(locale, "closeToast")}>
        ×
      </button>
    </div>
  );
}

function scrollToFirstFieldError(fieldIds: string[]) {
  const first = fieldIds.find(Boolean);
  if (!first) return;
  const el = document.getElementById(`field_${first}`) as HTMLElement | null;
  if (el && typeof el.scrollIntoView === "function") {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  window.setTimeout(() => {
    if (el && typeof el.focus === "function") {
      el.focus();
    }
  }, 350);
}

function SchemaField({
  field,
  value,
  onChange,
  error,
  disabled,
  locale
}: {
  field: FieldSchema;
  value: unknown;
  onChange: (next: unknown) => void;
  error?: string;
  disabled: boolean;
  locale: string;
}) {
  const errId = `err_${field.id}`;

  if (field.type === "number") {
    return (
      <NumberInput
        id={`field_${field.id}`}
        label={field.label}
        required={field.required}
        helpText={field.help_text}
        errorId={errId}
        error={error}
        disabled={disabled}
        value={value === "" || value === undefined || value === null ? "" : String(value)}
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "" ? "" : Number(v));
        }}
      />
    );
  }

  if (field.type === "select") {
    const opts = Array.isArray(field.options) ? field.options : [];
    const strVal = typeof value === "string" ? value : "";
    return (
      <SelectField
        id={`field_${field.id}`}
        label={field.label}
        required={field.required}
        helpText={field.help_text}
        errorId={errId}
        error={error}
        placeholder={field.required ? t(locale, "selectPlaceholder") : t(locale, "selectPlaceholderOptional")}
        disabled={disabled}
        value={strVal}
        onChange={(e) => onChange(e.target.value)}
      >
        {opts.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </SelectField>
    );
  }

  return (
    <TextInput
      id={`field_${field.id}`}
      label={field.label}
      required={field.required}
      helpText={field.help_text}
      errorId={errId}
      error={error}
      disabled={disabled}
      type="text"
      value={typeof value === "string" ? value : ""}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function FormPage() {
  const { inspectionId, uuid } = useParams();
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ kind: "error" | "success"; message: string } | null>(null);
  const [data, setData] = useState<GetFormResponse | null>(null);
  const [loadFailure, setLoadFailure] = useState<{ title: string; body: string } | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [outputLanguage, setOutputLanguage] = useState<string | null>(null);
  const [formLanguage, setFormLanguage] = useState<string>("en");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [logoBroken, setLogoBroken] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formLevelMessages, setFormLevelMessages] = useState<string[]>([]);
  const linkKeyRef = useRef<string>("");

  const ids = useMemo(() => {
    if (!inspectionId || !uuid) return null;
    return { inspectionId, uuid };
  }, [inspectionId, uuid]);

  const locale = formLanguage || "en";
  const branding = data?.branding ?? DEFAULT_BRANDING;
  const brandColor = branding.primary_color || "#1F2937";
  const logoSrc = resolveMediaUrl(branding.logo_url);
  const languageCodes = data?.output_languages?.length ? data.output_languages : [];
  const effectiveOutputLang =
    outputLanguage ?? data?.default_output_language ?? (languageCodes[0] ? languageCodes[0] : null) ?? "";
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

  const loadForm = useCallback(async () => {
    if (!ids) return;
    setLoading(true);
    setLoadFailure(null);
    setToast(null);
    try {
      const res = await getForm(ids.inspectionId, ids.uuid, formLanguage);
      setData(res);
      const effectiveFormLang = res.selected_content_language ?? formLanguage ?? res.default_output_language ?? "en";
      setFormLanguage(effectiveFormLang);

      const lk = `${ids.inspectionId}:${ids.uuid}`;
      if (linkKeyRef.current !== lk) {
        linkKeyRef.current = lk;
        setOutputLanguage(res.default_output_language ?? (res.output_languages?.[0] ?? null));
        setAnswers(buildInitialAnswers(res.schema));
      }
      setFieldErrors({});
      setFormLevelMessages([]);
    } catch (e: unknown) {
      setData(null);
      setLoadFailure(describeGetFormFailure(e, formLanguage || "en"));
    } finally {
      setLoading(false);
    }
  }, [ids, formLanguage]);

  useEffect(() => {
    if (!ids) {
      setLoading(false);
      return;
    }
    void loadForm();
  }, [ids, loadForm]);

  function clearFieldError(fieldId: string) {
    setFieldErrors((prev) => {
      if (!prev[fieldId]) return prev;
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ids || !data || submitting) return;
    setSubmitting(true);
    setToast(null);
    setFormLevelMessages([]);

    const clientMsgs = {
      requiredSelect: t(locale, "errorSelectRequired"),
      requiredText: t(locale, "errorTextRequired"),
      requiredNumber: t(locale, "errorNumberRequired"),
      invalidNumber: t(locale, "errorNumberInvalid")
    };
    const clientErrs = validateAnswersForSubmit(data.schema, answers, clientMsgs);
    if (Object.keys(clientErrs).length) {
      setFieldErrors(clientErrs);
      setFormLevelMessages([t(locale, "validationSummaryTitle")]);
      setSubmitting(false);
      scrollToFirstFieldError(Object.keys(clientErrs));
      return;
    }

    const payload = scrubAnswersForSubmit(data.schema, answers);

    try {
      await submitForm(ids.inspectionId, ids.uuid, payload, effectiveOutputLang || undefined);
      setSubmitted(true);
      setFieldErrors({});
    } catch (e: unknown) {
      if (isApiHttpError(e) && e.status === 400) {
        const mapped = mapServerValidationToFieldErrors(data.schema, e.detail, {
          missingSelect: t(locale, "errorSelectRequired"),
          missingText: t(locale, "errorTextRequired"),
          missingNumber: t(locale, "errorNumberRequired"),
          badNumber: t(locale, "errorNumberInvalid"),
          badText: t(locale, "errorBackendText"),
          badString: t(locale, "errorBackendString"),
          badOption: t(locale, "errorBackendOption"),
          unsupported: t(locale, "errorBackendUnsupported")
        });
        setFieldErrors(mapped.fieldErrors);
        const msgs = [t(locale, "validationSummaryTitle"), ...mapped.general];
        setFormLevelMessages(msgs);
        const fe = Object.keys(mapped.fieldErrors);
        if (fe.length) scrollToFirstFieldError(fe);
        else {
          window.setTimeout(() => document.getElementById("form-submit-summary")?.focus(), 0);
        }
      } else if (isApiHttpError(e) && e.status === 409) {
        try {
          const refreshed = await getForm(ids.inspectionId, ids.uuid, formLanguage);
          setData(refreshed);
          setSubmitted(false);
          setFieldErrors({});
          setFormLevelMessages([]);
        } catch {
          setFormLevelMessages([t(locale, "submitErrorTitle"), describeSubmitFailure(e, locale)]);
          window.setTimeout(() => document.getElementById("form-submit-summary")?.focus(), 0);
        }
      } else {
        setFormLevelMessages([t(locale, "submitErrorTitle"), describeSubmitFailure(e, locale)]);
        window.setTimeout(() => document.getElementById("form-submit-summary")?.focus(), 0);
      }
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

  const showLoadSpinner = loading && !data && !loadFailure;
  const showBlockingError = Boolean(!loading && loadFailure && !data);

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

      {data ? (
        <details className="referenceDetails referenceDetailsBelowHeader">
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

      {showLoadSpinner ? (
        <section className="card cardLoading" aria-labelledby="loading-heading">
          <h2 id="loading-heading" className="visuallyHidden">
            {t(locale, "loading")}
          </h2>
          <LoadingState label={t(locale, "loading")} />
        </section>
      ) : null}

      {showBlockingError && loadFailure ? (
        <section className="card" aria-live="assertive">
          <Alert variant="danger" title={loadFailure.title} role="alert">
            <p className="alertText">{loadFailure.body}</p>
            <div className="stackRow">
              <Button type="button" variant="primary" onClick={() => void loadForm()}>
                {t(locale, "retryLoad")}
              </Button>
            </div>
          </Alert>
        </section>
      ) : null}

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
              <Button type="button" variant="primary" onClick={() => void onDownloadPdf()} disabled={pdfDownloading}>
                {pdfDownloading ? t(locale, "downloadingPdf") : t(locale, "downloadPdf")}
              </Button>
            </div>
          ) : completionKnown && orgPresent ? (
            <p className="muted small completionNote">{t(locale, "pdfNotAvailableNote")}</p>
          ) : null}
        </section>
      ) : null}

      {showInteractiveForm && data ? (
        <form
          onSubmit={onSubmit}
          className={`card formCard${loading && data ? " formCardRefreshing" : ""}`}
          noValidate
          aria-busy={submitting}
        >
          {loading && data ? (
            <div className="formRefreshBanner" role="status" aria-live="polite">
              {t(locale, "updatingQuestionnaire")}
            </div>
          ) : null}

          {formLevelMessages.length ? (
            <div
              className="formSummaryErrors"
              role="alert"
              aria-live="assertive"
              id="form-submit-summary"
              tabIndex={-1}
            >
              <div className="formSummaryTitle">{formLevelMessages[0]}</div>
              {formLevelMessages.length > 1 ? (
                <ul className="formSummaryList">
                  {formLevelMessages.slice(1).map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              ) : null}
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
                <label htmlFor="form_language" className="fieldLabel">
                  {t(locale, "formLanguage")}
                </label>
                <select
                  id="form_language"
                  className="selectControl"
                  value={formLanguage}
                  onChange={(e) => setFormLanguage(e.target.value || (data.default_output_language ?? "en"))}
                  disabled={submitting}
                  aria-describedby="form_language_hint"
                >
                  {languageCodes.map((lang) => (
                    <option key={lang} value={lang}>
                      {languageLabel(lang)}
                    </option>
                  ))}
                </select>
                <span id="form_language_hint" className="fieldHint">
                  {t(locale, "formLanguageHint")}
                </span>
              </div>
              <div className="field fieldLang">
                <label htmlFor="output_language" className="fieldLabel">
                  {t(locale, "outputLanguage")}
                </label>
                <select
                  id="output_language"
                  className="selectControl"
                  value={effectiveOutputLang}
                  onChange={(e) => setOutputLanguage(e.target.value || null)}
                  disabled={submitting}
                  aria-describedby="output_language_hint"
                >
                  {languageCodes.map((lang) => (
                    <option key={`out-${lang}`} value={lang}>
                      {languageLabel(lang)}
                    </option>
                  ))}
                </select>
                <span id="output_language_hint" className="fieldHint">
                  {t(locale, "outputLanguageHint")}
                </span>
              </div>
            </div>
          ) : null}

          {data.schema.sections.map((s) => (
            <div key={s.id} className="section">
              <h3 className="sectionTitle">{s.title}</h3>
              {s.fields.map((f) => (
                <div key={f.id} className="fieldAnchor" data-field-anchor={f.id}>
                  <SchemaField
                    field={f}
                    value={answers[f.id]}
                    onChange={(next) => {
                      setAnswers((prev) => ({ ...prev, [f.id]: next }));
                      clearFieldError(f.id);
                    }}
                    error={fieldErrors[f.id]}
                    disabled={submitting}
                    locale={locale}
                  />
                </div>
              ))}
            </div>
          ))}

          <div className="actions">
            <Button type="submit" variant="primary" disabled={submitting || (loading && !!data)}>
              {submitting ? t(locale, "submitting") : t(locale, "submit")}
            </Button>
          </div>
        </form>
      ) : null}

      {branding.footer_text ? <div className="muted small brandFooter">{branding.footer_text}</div> : null}
    </div>
  );
}