import React from 'react';
import { motion } from 'framer-motion';

interface GodLoadingIndicatorProps {
  message?: string;
}

/**
 * Minimal, professional loading indicator for God Mode AI analysis
 * Clean and elegant - just breathing text with animated ellipsis
 */
export const GodLoadingIndicator: React.FC<GodLoadingIndicatorProps> = ({
  message = "God is watching"
}) => {
  return (
    <div className="flex items-center justify-center py-8">
      {/* Minimal breathing text with subtle glow */}
      <motion.div
        className="text-2xl font-medium text-[#FF6B35]"
        animate={{
          opacity: [0.6, 1, 0.6],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        style={{
          textShadow: '0 0 20px rgba(255, 107, 53, 0.3)',
        }}
      >
        {message}
        {/* Animated ellipsis dots */}
        <motion.span
          animate={{
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0
          }}
        >
          .
        </motion.span>
        <motion.span
          animate={{
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.3
          }}
        >
          .
        </motion.span>
        <motion.span
          animate={{
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.6
          }}
        >
          .
        </motion.span>
      </motion.div>
    </div>
  );
};
