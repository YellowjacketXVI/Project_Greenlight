"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Play, Check, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth";
import { useProjectsStore } from "@/store/projects";
import { writerApi } from "@/lib/api";

const LAYERS = [
  { id: 1, name: "High-Level Outline", key: "high_level_outline" },
  { id: 2, name: "User Review", key: "user_checkpoint_1" },
  { id: 3, name: "Granular Outline", key: "granular_outline" },
  { id: 4, name: "User Review", key: "user_checkpoint_2" },
  { id: 5, name: "Scale Analysis", key: "scale_determination" },
  { id: 6, name: "Write Out", key: "write_out" },
];

export default function ProjectPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  const { user, checkSession } = useAuthStore();
  const { currentProject, outlines, selectProject, isLoading } = useProjectsStore();

  const [currentLayer, setCurrentLayer] = useState(1);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStatus, setGenerationStatus] = useState<string>("");
  const [generationError, setGenerationError] = useState<string | null>(null);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
    }
  }, [projectId, selectProject]);

  const getLayerStatus = (layerId: number) => {
    const outline = outlines.find((o) => o.layer === layerId);
    if (!outline) return "pending";
    return outline.status;
  };

  const handleStartWriting = async () => {
    const { token } = useAuthStore.getState();
    if (!token) {
      setGenerationError("Please log in to generate content. Redirecting to login...");
      setTimeout(() => router.push("/"), 2000);
      return;
    }

    setIsGenerating(true);
    setGenerationError(null);
    setGenerationStatus("Starting writer pipeline...");

    try {
      // Start the writer pipeline
      setGenerationStatus("Initializing outline generation...");
      console.log("Calling writer API start with project:", projectId);
      const startResult = await writerApi.start(projectId, token);
      console.log("Start result:", startResult);

      // Generate the first layer
      setGenerationStatus("Generating high-level outline with AI... This may take a minute.");
      console.log("Calling writer API generate");
      const result = await writerApi.generate(projectId, token);
      console.log("Generate result:", result);

      setGenerationStatus("Outline generated successfully!");
      setCurrentLayer(2);

      // Refresh outlines
      await selectProject(projectId);
    } catch (error) {
      console.error("Generation error:", error);
      const errorMessage = (error as Error).message || "Failed to generate outline";
      setGenerationError(errorMessage);

      // If auth error, redirect to login
      if (errorMessage.includes("401") || errorMessage.includes("auth") || errorMessage.includes("token")) {
        setTimeout(() => router.push("/"), 2000);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  if (isLoading || !currentProject) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar - Layer Progress */}
      <aside className="w-64 border-r bg-card p-4">
        <Button
          variant="ghost"
          size="sm"
          className="mb-6"
          onClick={() => router.push("/dashboard")}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        <h2 className="font-semibold mb-4">Writing Layers</h2>

        <div className="space-y-2">
          {LAYERS.map((layer) => {
            const status = getLayerStatus(layer.id);
            return (
              <div
                key={layer.id}
                className={`flex items-center gap-3 p-2 rounded-md ${
                  currentLayer === layer.id ? "bg-primary/10" : ""
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                    status === "approved" || status === "completed"
                      ? "bg-green-500 text-white"
                      : status === "active"
                      ? "bg-primary text-white"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {status === "approved" || status === "completed" ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    layer.id
                  )}
                </div>
                <span className="text-sm">{layer.name}</span>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold mb-2">{currentProject.title}</h1>
          <p className="text-muted-foreground mb-6">
            {currentProject.genre || "No genre"} • {currentProject.status}
          </p>

          {/* Prompt Display */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Story Prompt</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{currentProject.prompt}</p>
            </CardContent>
          </Card>

          {/* Error Display */}
          {generationError && (
            <Card className="mb-6 border-destructive">
              <CardContent className="py-4">
                <div className="flex items-center gap-2 text-destructive">
                  <X className="h-5 w-5" />
                  <span>{generationError}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Action Area */}
          {currentLayer === 1 && !isGenerating && (
            <Card>
              <CardContent className="py-8 text-center">
                <h3 className="text-lg font-medium mb-4">Ready to Start Writing</h3>
                <p className="text-muted-foreground mb-6">
                  Click below to generate your high-level story outline
                </p>
                <Button size="lg" onClick={handleStartWriting}>
                  <Play className="h-4 w-4 mr-2" />
                  Generate Outline
                </Button>
              </CardContent>
            </Card>
          )}

          {isGenerating && (
            <Card>
              <CardContent className="py-8 text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
                <h3 className="text-lg font-medium">Generating...</h3>
                <p className="text-muted-foreground">
                  {generationStatus || "Creating your story outline with AI"}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}

