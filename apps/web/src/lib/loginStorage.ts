const ADMIN_EMAIL_KEY = "ai_dev_remember_admin_email";
const COMPANY_EMAIL_KEY = "ai_dev_remember_company_email";

export function getRememberedAdminEmail() {
  return localStorage.getItem(ADMIN_EMAIL_KEY) ?? "";
}

export function setRememberedAdminEmail(email: string, remember: boolean) {
  if (remember) {
    localStorage.setItem(ADMIN_EMAIL_KEY, email);
  } else {
    localStorage.removeItem(ADMIN_EMAIL_KEY);
  }
}

export function getRememberedCompanyEmail(slug: string) {
  try {
    const map = JSON.parse(localStorage.getItem(COMPANY_EMAIL_KEY) ?? "{}") as Record<string, string>;
    return map[slug] ?? "";
  } catch {
    return "";
  }
}

export function setRememberedCompanyEmail(slug: string, email: string, remember: boolean) {
  try {
    const map = JSON.parse(localStorage.getItem(COMPANY_EMAIL_KEY) ?? "{}") as Record<string, string>;
    if (remember) {
      map[slug] = email;
    } else {
      delete map[slug];
    }
    localStorage.setItem(COMPANY_EMAIL_KEY, JSON.stringify(map));
  } catch {
    if (remember) {
      localStorage.setItem(COMPANY_EMAIL_KEY, JSON.stringify({ [slug]: email }));
    }
  }
}
