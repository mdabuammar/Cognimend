import React from "react";
import { ShieldCheck, Lock, Eye, ShieldAlert, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

export default function SecurityPage() {
  return (
    <div className="min-h-screen bg-[#020817] text-white">
      <div className="max-w-7xl mx-auto px-4 py-20">
        <h1 className="text-5xl font-black mb-8 tracking-tight">Security & Trust</h1>
        <p className="text-slate-400 text-xl max-w-2xl mb-12">
          Enterprise-grade protection for your data and models. Cognimend is built on a foundation of strict isolation and audited transparency.
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <SecurityCard 
            title="SaaS Isolation" 
            desc="Every workspace is logically isolated. Your data never mixes with other tenants."
            icon={ShieldCheck}
          />
          <SecurityCard 
            title="RBAC / ABAC" 
            desc="Granular permission control down to the document level."
            icon={Lock}
          />
          <SecurityCard 
            title="Audit Vault" 
            desc="Every administrative action is logged in an immutable audit trail."
            icon={Eye}
          />
          <SecurityCard 
            title="Zero Trust Gateway" 
            desc="Proprietary gateway strips all client identity headers for absolute security."
            icon={ShieldAlert}
          />
        </div>
        
        <div className="mt-20 p-12 bg-white/[0.02] border border-white/[0.05] rounded-[40px] text-center">
          <h2 className="text-2xl font-bold mb-4">Ready to secure your knowledge?</h2>
          <Link to="/signup" className="inline-block px-8 py-4 bg-indigo-600 hover:bg-indigo-500 rounded-2xl font-bold transition-all">
            Get Started
          </Link>
        </div>
      </div>
    </div>
  );
}

function SecurityCard({ title, desc, icon: Icon }: { title: string; desc: string; icon: LucideIcon }) {
  return (
    <div className="p-8 bg-white/[0.03] border border-white/[0.08] rounded-3xl">
      <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center mb-6 text-indigo-400">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      <p className="text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}
