import { useState } from "react";
import { Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
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
  const [searchParams] = useSearchParams();
  const fromDemo = searchParams.get("from") === "demo";
  const from = fromDemo ? "/trial/setup" : location.state?.from || "/dashboard";

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
    <div className="auth-shell min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md" data-testid="login-page">
        <div className="flex items-center gap-2.5 mb-10">
          <div className="w-10 h-10 rounded-md bg-[#2d5a27] flex items-center justify-center">
            <Trees className="w-5 h-5 text-white" strokeWidth={1.7} />
          </div>
          <div>
            <div className="font-bold text-base">ForestWatch</div>
            <div className="text-[10px] tracking-[0.22em] uppercase text-[#7b827b]">
              Forest intelligence
            </div>
          </div>
        </div>

        <h2 className="text-3xl font-bold tracking-tight mb-2">Sign in</h2>
        <p className="text-[#4a524a] mb-8">
          Continue monitoring forests for your organization. Review what changed,
          why it matters, and what requires attention.
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
            Start a 14-day trial
          </Link>
          <span className="mx-2 text-[#c5c9c0]">·</span>
          <Link
            to="/explore"
            data-testid="goto-explore"
            className="text-[#2d5a27] font-semibold hover:underline"
          >
            Explore the demo
          </Link>
        </div>
      </div>
    </div>
  );
}
