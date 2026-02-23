import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowRight, Mail, Upload, Send, CreditCard } from "lucide-react";
import { Button } from "./button";

const tourSteps = [
  {
    target: "nav-accounts",
    title: "Connect Email Accounts",
    description: "Start by connecting your sending accounts. You can add multiple SMTP accounts to rotate between.",
    icon: Mail,
    position: "right",
  },
  {
    target: "nav-email-lists",
    title: "Upload Your Lists",
    description: "Upload your contacts via CSV. You can manage multiple lists and use dynamic variables.",
    icon: Upload,
    position: "right",
  },
  {
    target: "nav-campaign",
    title: "Start Campaign",
    description: "Create and launch your first campaign. Schedule it for later or send immediately.",
    icon: Send,
    position: "right",
  },
  {
    target: "nav-subscription",
    title: "Monitor Usage",
    description: "Track your usage and upgrade anytime to unlock higher sending limits.",
    icon: CreditCard,
    position: "right",
  },
];

export default function OnboardingTour({ isOpen, onComplete, onSkip }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightPosition, setHighlightPosition] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    
    const updatePosition = () => {
      const targetElement = document.querySelector(`[data-testid="${tourSteps[currentStep].target}"]`);
      if (targetElement) {
        const rect = targetElement.getBoundingClientRect();
        setHighlightPosition({
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
        });
      }
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    return () => window.removeEventListener("resize", updatePosition);
  }, [isOpen, currentStep]);

  const handleNext = () => {
    if (currentStep < tourSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      onComplete();
    }
  };

  const handleSkip = () => {
    onSkip();
  };

  if (!isOpen) return null;

  const step = tourSteps[currentStep];
  const Icon = step.icon;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100]"
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" />

        {/* Highlight cutout */}
        {highlightPosition && (
          <div
            className="absolute bg-transparent rounded-lg ring-4 ring-blue-500 ring-offset-4 ring-offset-transparent transition-all duration-300"
            style={{
              top: highlightPosition.top - 4,
              left: highlightPosition.left - 4,
              width: highlightPosition.width + 8,
              height: highlightPosition.height + 8,
              boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.7)",
            }}
          />
        )}

        {/* Tooltip */}
        {highlightPosition && (
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="absolute bg-white rounded-xl shadow-2xl p-6 w-80"
            style={{
              top: Math.max(20, highlightPosition.top - 20),
              left: highlightPosition.left + highlightPosition.width + 24,
            }}
          >
            {/* Close button */}
            <button
              onClick={handleSkip}
              className="absolute top-3 right-3 text-slate-400 hover:text-slate-600"
            >
              <X size={18} />
            </button>

            {/* Step indicator */}
            <div className="flex gap-1 mb-4">
              {tourSteps.map((_, index) => (
                <div
                  key={index}
                  className={`h-1 flex-1 rounded-full transition-colors ${
                    index <= currentStep ? "bg-blue-500" : "bg-slate-200"
                  }`}
                />
              ))}
            </div>

            {/* Content */}
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Icon size={20} className="text-blue-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900 mb-1">{step.title}</h3>
                <p className="text-sm text-slate-600">{step.description}</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between">
              <button
                onClick={handleSkip}
                className="text-sm text-slate-500 hover:text-slate-700"
              >
                Skip tour
              </button>
              <Button
                size="sm"
                onClick={handleNext}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {currentStep < tourSteps.length - 1 ? (
                  <>
                    Next
                    <ArrowRight size={14} className="ml-1" />
                  </>
                ) : (
                  "Finish"
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
