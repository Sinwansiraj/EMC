"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/utils/supabase/client";

function Confirm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/get-started";
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const supabase = createClient();

    (async () => {
      try {
        // 1) PKCE flow: ?code=… in the query string.
        const code = params.get("code");
        if (code) {
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (!error) return router.replace(next);
        }

        // 2) Implicit flow: tokens in the URL hash (#access_token=…&refresh_token=…).
        if (typeof window !== "undefined" && window.location.hash) {
          const h = new URLSearchParams(window.location.hash.replace(/^#/, ""));
          const access_token = h.get("access_token");
          const refresh_token = h.get("refresh_token");
          if (access_token && refresh_token) {
            const { error } = await supabase.auth.setSession({ access_token, refresh_token });
            if (!error) return router.replace(next);
          }
        }

        // 3) The browser client may have already detected the session from the URL.
        const { data } = await supabase.auth.getSession();
        if (data.session) return router.replace(next);

        setFailed(true);
      } catch {
        setFailed(true);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (failed) {
    return (
      <div className="empty">
        That sign-in link didn&apos;t work or has expired.{" "}
        <a href="/login">Request a new one</a>.
      </div>
    );
  }
  return <div className="empty">Signing you in…</div>;
}

export default function Page() {
  return (
    <Suspense fallback={<div className="empty">Signing you in…</div>}>
      <Confirm />
    </Suspense>
  );
}
