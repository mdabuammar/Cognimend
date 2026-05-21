import { useState } from "react";
import { motion } from "framer-motion";
import { User, Mail, Lock, Link2, Unlink, LogOut } from "lucide-react";
import { PageHeader } from "@/components/ui/cognimend";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

function SettingsSection({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export default function AccountPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState({ name: "Admin User", email: "admin@cognimend.ai" });
  const [googleConnected] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 800));
    setSaving(false);
    toast.success("Profile updated");
  };

  return (
    <div>
      <PageHeader title="Account" subtitle="Manage your profile and login methods" />

      <div className="space-y-4 max-w-2xl">
        {/* Profile */}
        <SettingsSection title="Profile" description="Your public identity on Cognimend">
          <div className="flex items-center gap-4 mb-5">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-lg font-bold text-white">AU</span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">{profile.name}</p>
              <p className="text-xs text-slate-400">{profile.email}</p>
            </div>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name</label>
              <input
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Email</label>
              <input
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors"
              />
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-sm font-semibold transition-colors"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </SettingsSection>

        {/* Password */}
        <SettingsSection title="Password" description="Change your account password">
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Current password</label>
              <input type="password" placeholder="••••••••" className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">New password</label>
              <input type="password" placeholder="Min. 8 characters" className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors" />
            </div>
            <button className="px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.08] text-white text-sm font-medium transition-colors border border-white/[0.08]">
              Update password
            </button>
          </div>
        </SettingsSection>

        {/* Connected Methods */}
        <SettingsSection title="Login Methods" description="Manage how you sign in to Cognimend">
          {/* Manual */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] mb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Mail className="w-4 h-4 text-indigo-400" />
              </div>
              <div>
                <p className="text-sm text-white">Email & Password</p>
                <p className="text-xs text-slate-400">{profile.email}</p>
              </div>
            </div>
            <span className="text-xs text-emerald-400 font-medium">Connected</span>
          </div>

          {/* Google */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-white/[0.06] border border-white/[0.08] flex items-center justify-center">
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
              </div>
              <div>
                <p className="text-sm text-white">Google Account</p>
                <p className="text-xs text-slate-400">
                  {googleConnected ? "Connected" : "Not connected"}
                </p>
              </div>
            </div>
            {googleConnected ? (
              <button className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors">
                <Unlink className="w-3.5 h-3.5" /> Unlink
              </button>
            ) : (
              <button className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors">
                <Link2 className="w-3.5 h-3.5" /> Link Google
              </button>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Linking Google allows you to sign in with "Continue with Google" without entering your password.
          </p>
        </SettingsSection>

        {/* Danger Zone */}
        <SettingsSection title="Sign Out">
          <button
            onClick={() => navigate("/login")}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 text-sm font-medium transition-colors"
          >
            <LogOut className="w-4 h-4" /> Sign out of Cognimend
          </button>
        </SettingsSection>
      </div>
    </div>
  );
}
