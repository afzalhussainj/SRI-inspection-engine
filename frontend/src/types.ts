export type FieldType = "text" | "number" | "select";

export type FieldSchema = {
  id: string;
  type: FieldType;
  label: string;
  help_text?: string;
  required: boolean;
  options?: Array<{ value: string; label: string }>;
  /** When present, initialize answers only if the value is valid for the field type and select options. */
  default?: string | number | null;
};

export type SectionSchema = {
  id: string;
  title: string;
  fields: FieldSchema[];
};

export type FormSchema = {
  title: string;
  sections: SectionSchema[];
};

export type GetFormResponse = {
  inspection_id: string;
  link_uuid: string;
  config_version_id: string;
  expires_at: string | null;
  already_submitted: boolean;
  schema: FormSchema;
  output_languages?: string[];
  default_output_language?: string;
  selected_content_language?: string;
  branding?: {
    organization_id: string;
    hospital_program_name: string;
    logo_url: string | null;
    primary_color: string;
    tagline: string;
    footer_text: string;
  };
};

export type SubmitResponse = {
  inspection_id: string;
  link_uuid: string;
  status: "submitted";
};


