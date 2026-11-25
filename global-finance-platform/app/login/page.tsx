"use client";

import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Activity, LockKeyhole, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) { setError("登入失敗，請確認帳號密碼或聯絡管理者。"); setBusy(false); return; }
    window.location.assign("/dashboard");
  }

  return <main className="authShell">
    <section className="authCard">
      <div className="brandMark"><Activity size={24}/></div>
      <p className="eyebrow">PRIVATE FINANCIAL WORKSPACE</p>
      <h1>GLOBAL <span>RADAR</span></h1>
      <p className="muted">全球金融市場智慧分析平台</p>
      <div className="secureNote"><ShieldCheck size={17}/> 私人工作區・僅限授權帳號登入</div>
      <form onSubmit={signIn} className="loginForm">
        <label>電子郵件<input type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@example.com"/></label>
        <label>密碼<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="輸入密碼"/></label>
        {error && <p className="errorText" role="alert">{error}</p>}
        <button className="primaryButton" disabled={busy}>{busy ? "登入中…" : <><LockKeyhole size={17}/> 安全登入</>}</button>
      </form>
      <p className="footHint">此平台不開放公開註冊。帳號由管理者於 Supabase 後台建立。</p>
    </section>
  </main>;
}