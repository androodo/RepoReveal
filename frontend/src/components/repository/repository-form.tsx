"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, createAnalysis } from "@/lib/api";
import { githubUrlSchema } from "@/lib/github-url";

const formSchema = z.object({
  repositoryUrl: githubUrlSchema,
});

type FormValues = z.infer<typeof formSchema>;

export function RepositoryForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const demoUrl =
    process.env.NEXT_PUBLIC_DEMO_REPOSITORY_URL || "https://github.com/tiangolo/fastapi";

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { repositoryUrl: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      const result = await createAnalysis(values.repositoryUrl);
      router.push(`/analyses/${result.analysis_id}`);
    } catch (error) {
      setSubmitError(
        error instanceof ApiError ? error.message : "Could not start analysis.",
      );
    }
  });

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          aria-label="GitHub repository URL"
          placeholder="https://github.com/owner/repository"
          {...register("repositoryUrl")}
        />
        <Button type="submit" disabled={isSubmitting} className="shrink-0">
          {isSubmitting ? "Starting…" : "Analyze Repository"}
        </Button>
      </div>
      {(errors.repositoryUrl || submitError) && (
        <p className="text-sm text-red-600 dark:text-red-400" role="alert">
          {errors.repositoryUrl?.message || submitError}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Button
          type="button"
          variant="secondary"
          onClick={() => setValue("repositoryUrl", demoUrl, { shouldValidate: true })}
        >
          Use example repository
        </Button>
        <span className="rounded border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]">
          Python only
        </span>
      </div>
    </form>
  );
}
