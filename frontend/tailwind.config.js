module.exports = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(240, 6%, 80%)",
        input: "hsl(240, 7%, 90%)",
        ring: "hsl(214, 77%, 46%)",
        background: "hsl(229, 52%, 16%)",
        foreground: "hsl(0, 0%, 100%)",
        primary: {
          DEFAULT: "hsl(229, 52%, 16%)",
          foreground: "hsl(0, 0%, 100%)",
        },
        secondary: {
          DEFAULT: "hsl(229, 40%, 22%)",
          foreground: "hsl(0, 0%, 100%)",
        },
        tertiary: {
          DEFAULT: "hsl(214, 77%, 46%)",
          foreground: "hsl(0, 0%, 100%)",
        },
        neutral: {
          DEFAULT: "hsl(0, 0%, 96%)",
          foreground: "hsl(229, 20%, 22%)",
        },
        destructive: {
          DEFAULT: "hsl(0, 84%, 60%)",
          foreground: "hsl(0, 0%, 100%)",
        },
        muted: {
          DEFAULT: "hsl(240, 7%, 90%)",
          foreground: "hsl(240, 5%, 35%)",
        },
        accent: {
          DEFAULT: "hsl(214, 77%, 46%)",
          foreground: "hsl(0, 0%, 100%)",
        },
        popover: {
          DEFAULT: "hsl(0, 0%, 100%)",
          foreground: "hsl(229, 20%, 22%)",
        },
        card: {
          DEFAULT: "hsl(0, 0%, 96%)",
          foreground: "hsl(229, 20%, 22%)",
        },
        success: "hsl(142, 43%, 45%)",
        warning: "hsl(33, 94%, 54%)",
        gray: {
          50: "hsl(0, 0%, 98%)",
          100: "hsl(240, 9%, 96%)",
          200: "hsl(240, 7%, 90%)",
          300: "hsl(240, 6%, 80%)",
          400: "hsl(240, 5%, 65%)",
          500: "hsl(240, 4%, 50%)",
          600: "hsl(240, 5%, 35%)",
          700: "hsl(240, 5%, 25%)",
          800: "hsl(240, 6%, 18%)",
          900: "hsl(240, 8%, 12%)",
        },
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        headline: ['"DM Sans"', "sans-serif"],
      },
      fontSize: {
        xs: "0.75rem",
        sm: "0.875rem",
        base: "1rem",
        lg: "1.25rem",
        xl: "1.563rem",
        "2xl": "1.953rem",
        "3xl": "2.441rem",
        "4xl": "3.052rem",
      },
      spacing: {
        '4': '1rem',
        '8': '2rem',
        '12': '3rem',
        '16': '4rem',
        '24': '6rem',
        '32': '8rem',
        '48': '12rem',
        '64': '16rem',
      },
      borderRadius: {
        lg: "1rem",
        md: "0.75rem",
        sm: "0.5rem",
      },
      backgroundImage: {
        'gradient-1': "linear-gradient(135deg, hsl(229, 52%, 16%) 0%, hsl(229, 45%, 22%) 100%)",
        'gradient-2': "linear-gradient(90deg, hsl(214, 77%, 46%) 0%, hsl(228, 61%, 35%) 100%)",
        'button-border-gradient': "linear-gradient(45deg, hsl(214, 77%, 46%) 0%, hsl(229, 52%, 16%) 100%)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(-10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "shake": {
          "0%, 100%": { transform: "translateX(0)" },
          "10%, 30%, 50%, 70%, 90%": { transform: "translateX(-4px)" },
          "20%, 40%, 60%, 80%": { transform: "translateX(4px)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out",
        "shake": "shake 0.5s ease-in-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
