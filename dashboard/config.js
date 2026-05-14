// Public Supabase config — anon key only. Populated by the deploy
// workflow from GitHub Actions Variables (not Secrets), or edit
// locally before running.
//
// Safe to commit: with RLS enabled this key only allows the policies
// we declared (select * + update status). Never put the service key
// here.
//
// Setting the dashboard secret (any non-empty value) gates access
// client-side. Acceptable for a personal tool; not real auth.

window.__CJW_CONFIG__ = {
  SUPABASE_URL: "REPLACE_ME_SUPABASE_URL",
  SUPABASE_ANON_KEY: "REPLACE_ME_SUPABASE_ANON_KEY",
  DASHBOARD_SECRET: "",  // empty = no gate
};
