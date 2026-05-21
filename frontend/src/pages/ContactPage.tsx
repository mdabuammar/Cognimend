import React from "react";
import { Mail, MessageSquare, Globe, Phone } from "lucide-react";

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-[#020817] text-white">
      <div className="max-w-7xl mx-auto px-4 py-20">
        <h1 className="text-5xl font-black mb-8 tracking-tight">Contact Sales & Support</h1>
        <p className="text-slate-400 text-xl max-w-2xl mb-12">
          Have questions about our enterprise plans? Our team is here to help you scale your RAG operations.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          <div className="space-y-8">
            <ContactInfo icon={Mail} label="Sales" value="sales@cognimend.com" />
            <ContactInfo icon={MessageSquare} label="Support" value="support@cognimend.com" />
            <ContactInfo icon={Phone} label="Enterprise" value="+1 (555) 000-0000" />
            <ContactInfo icon={Globe} label="HQ" value="San Francisco, CA" />
          </div>

          <form className="p-10 bg-white/[0.03] border border-white/[0.08] rounded-[40px] space-y-6">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">First Name</label>
                <input type="text" className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:outline-none focus:border-indigo-500/50" />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">Last Name</label>
                <input type="text" className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:outline-none focus:border-indigo-500/50" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-slate-500">Business Email</label>
              <input type="email" className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:outline-none focus:border-indigo-500/50" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-slate-500">Message</label>
              <textarea rows={4} className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:outline-none focus:border-indigo-500/50" />
            </div>
            <button className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 rounded-2xl font-bold transition-all shadow-xl shadow-indigo-600/20">
              Send Inquiry
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function ContactInfo({ icon: Icon, label, value }: any) {
  return (
    <div className="flex items-center gap-6 p-6 bg-white/[0.02] border border-white/[0.05] rounded-3xl group hover:bg-white/[0.04] transition-all">
      <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 mb-1">{label}</div>
        <div className="text-xl font-bold text-white">{value}</div>
      </div>
    </div>
  );
}
