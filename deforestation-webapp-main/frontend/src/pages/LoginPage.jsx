import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Trees, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/dashboard";

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const res = await login(email, password);
    setLoading(false);
    if (res.ok) {
      toast.success(`Welcome back, ${res.user.name}`);
      navigate(from, { replace: true });
    } else {
      setError(res.error);
    }
  };

  return (
    <div className="auth-shell min-h-screen flex flex-col md:flex-row">
      {/* Left: hero image */}
      <div
        className="hidden md:block md:w-1/2 relative bg-cover bg-center"
        style={{
          backgroundImage:
            "url('https://images.unsplash.com/photo-1759681770982-313332e7f42c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njl8MHwxfHNlYXJjaHwzfHxzYXRlbGxpdGUlMjB2aWV3JTIwZm9yZXN0fGVufDB8fHx8MTc4MDc3NjU1Nnww&ixlib=rb-4.1.0&q=85')",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1e1a]/70 via-[#2d5a27]/40 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-12 text-white">
          <div className="text-xs tracking-[0.3em] uppercase mb-3 text-white/80">
            ForestWatch · Monitoring
          </div>
          <h1 className="text-4xl lg:text-5xl font-bold leading-[1.05] mb-4">
            See every hectare.
            <br />
            Defend every tree.
          </h1>
          <p className="text-white/85 max-w-md leading-relaxed">
            A clean-architecture platform for satellite-grade deforestation
            intelligence — open, scalable, and extensible.
          </p>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md">
          <div className="flex items-center gap-2.5 mb-10">
            <div className="w-10 h-10 rounded-md bg-[#2d5a27] flex items-center justify-center">
              <Trees className="w-5 h-5 text-white" strokeWidth={1.7} />
            </div>
            <div>
              <div className="font-bold text-base">ForestWatch</div>
              <div className="text-[10px] tracking-[0.22em] uppercase text-[#7b827b]">
                Sign in to continue
              </div>
            </div>
          </div>

          <h2 className="text-3xl font-bold tracking-tight mb-2">Welcome back</h2>
          <p className="text-[#4a524a] mb-8">
            Sign in to access the monitoring dashboard and live map.
          </p>

          <form onSubmit={onSubmit} className="space-y-5" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                data-testid="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@organization.org"
                required
                className="bg-white border-[#eaece6] h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="bg-white border-[#eaece6] h-11"
              />
            </div>

            {error && (
              <div
                data-testid="login-error"
                className="text-sm text-[#9b2226] bg-[#9b2226]/8 border border-[#9b2226]/20 rounded-md px-3 py-2"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              data-testid="login-submit"
              disabled={loading}
              className="w-full h-11 bg-[#2d5a27] hover:bg-[#21421d] text-white font-medium"
            >
              {loading ? "Signing in…" : "Sign in"}
              <ArrowRight className="w-4 h-4 ml-2" strokeWidth={1.7} />
            </Button>
          </form>

          <div className="mt-8 text-sm text-[#4a524a]">
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              data-testid="goto-register"
              className="text-[#2d5a27] font-semibold hover:underline"
            >
              Create one
            </Link>
          </div>

          <div className="mt-10 pt-6 border-t border-[#eaece6] text-xs text-[#7b827b]">
            <div className="label-eyebrow mb-2">Demo credentials</div>
            <code className="font-mono text-[11px]">admin@forestwatch.io / ForestAdmin2026!</code>
          </div>
        </div>
      </div>
    </div>
  );
}
