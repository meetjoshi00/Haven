"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import AnimatedOrb from "@/components/ui/animated-orb";

export default function AuthPage() {
  const [email, setEmail] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    setSent(true);
  }

  return (
    <div className="flex min-h-screen">
      <div className="flex flex-1 flex-col justify-center px-8 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <h1 className="mb-1 text-4xl font-bold">Haven</h1>
          <div className="mt-12">
            <h2 className="text-2xl font-bold">
              {isSignUp ? "Create your account" : "Login to your account"}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {isSignUp
                ? "Enter your email below to create an account"
                : "Enter your email below to login to your account"}
            </p>

            {sent ? (
              <div className="mt-8 rounded-lg border bg-secondary/50 p-6">
                <p className="font-medium">Check your email</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  We sent a login link to <strong>{email}</strong>. Click the
                  link in your email to sign in.
                </p>
                <Button
                  variant="ghost"
                  className="mt-4"
                  onClick={() => setSent(false)}
                >
                  Use a different email
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="m@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>

                {error && (
                  <p className="text-sm text-destructive">{error}</p>
                )}

                <Button
                  type="submit"
                  className="w-full text-white"
                  style={{ backgroundColor: '#282079' }}
                  disabled={loading || !email}
                >
                  {loading ? "Sending..." : "Login with email"}
                </Button>

                <p className="text-center text-sm text-muted-foreground">
                  {isSignUp ? (
                    <>
                      Already have an account?{" "}
                      <button
                        type="button"
                        className="font-medium text-primary underline-offset-4 hover:underline"
                        onClick={() => setIsSignUp(false)}
                      >
                        Sign in
                      </button>
                    </>
                  ) : (
                    <>
                      Don&apos;t have an account?{" "}
                      <button
                        type="button"
                        className="font-medium text-primary underline-offset-4 hover:underline"
                        onClick={() => setIsSignUp(true)}
                      >
                        Create one
                      </button>
                    </>
                  )}
                </p>
              </form>
            )}
          </div>
        </div>
      </div>

      <div className="hidden flex-1 items-center justify-center bg-secondary/30 lg:flex">
        <AnimatedOrb size={320} />
      </div>
    </div>
  );
}
