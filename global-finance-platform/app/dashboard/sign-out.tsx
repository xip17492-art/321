"use client";
import { LogOut } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export default function SignOutButton() {
  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.assign("/login");
  }
  return <button className="ghostButton" onClick={signOut}><LogOut size={16}/> 登出</button>;
}