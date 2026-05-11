"use client";

import Link from "next/link";

export default function SafeResponsePage() {
  return (
    <div className="flex h-screen items-center justify-center overflow-y-auto bg-[#F7F5F1] px-6 py-6">
      <div className="w-full max-w-lg">
        <h1 className="text-2xl font-bold">Let&apos;s take a pause</h1>

        <div className="mt-4 space-y-3 text-sm leading-relaxed">
          <p>It sounds like things might be feeling really hard right now.</p>
          <p>That matters more than any scenario.</p>
          <p>
            You don&apos;t have to be okay right now, and you don&apos;t have to
            keep going with the practice session.
          </p>
          <p>
            If you&apos;d like to talk to someone who can help, here are some
            options:
          </p>
        </div>

        <div className="mt-5 space-y-4 text-sm">
          <div>
            <h2 className="font-semibold">If you&apos;re in crisis right now:</h2>
            <ul className="mt-1.5 list-disc space-y-1 pl-5">
              <li>
                <strong>Crisis Text Line</strong> — Text HOME to 741741 (US, UK,
                Canada, Ireland)
              </li>
              <li>
                <strong>International Association for Suicide Prevention</strong>{" "}
                — find your country&apos;s crisis line at iasp.info
              </li>
            </ul>
          </div>

          <div>
            <h2 className="font-semibold">If you want to talk to someone:</h2>
            <ul className="mt-1.5 list-disc space-y-1 pl-5">
              <li>
                <strong>Samaritans (UK/Ireland)</strong> — 116 123 (free, 24/7)
              </li>
              <li>
                <strong>988 Suicide and Crisis Lifeline (US)</strong> — call or
                text 988
              </li>
              <li>
                <strong>Lifeline (Australia)</strong> — 13 11 14
              </li>
            </ul>
          </div>

          <div>
            <h2 className="font-semibold">
              If you&apos;re autistic and want to talk to someone who understands:
            </h2>
            <ul className="mt-1.5 list-disc space-y-1 pl-5">
              <li>
                <strong>Autistic Self Advocacy Network</strong> —
                autisticadvocacy.org
              </li>
              <li>
                <strong>Autism Society helpline</strong> — 1-800-328-8476
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-lg bg-foreground px-5 py-3 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
          >
            I&apos;m okay — take me back home
          </Link>
          <button
            onClick={() => {
              if (typeof window !== "undefined") window.close();
            }}
            className="inline-flex items-center justify-center rounded-lg border px-5 py-3 text-sm font-medium transition-colors hover:bg-accent"
          >
            Close the app for now
          </button>
        </div>
      </div>
    </div>
  );
}
