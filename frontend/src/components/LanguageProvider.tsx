"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Language = "en" | "ar";

const translations: Record<string, string> = {
  "Platform": "المنصة",
  "Geospatial AI Platform": "منصة ذكاء اصطناعي جغرافية",
  "How it Works": "كيف تعمل",
  "About": "عن معيار",
  "Validate Geospatial Data.": "تحقق من جودة البيانات الجغرافية.",
  "Make Reliable Decisions.": "اتخذ قرارات موثوقة.",
  "Detect spatial changes, validate map accuracy, identify inconsistencies, and generate AI-powered recommendations across satellite, aerial, and vector data.": "اكتشف التغيّرات المكانية، وتحقق من دقة الخرائط، وحدد حالات عدم الاتساق، وأنشئ توصيات مدعومة بالذكاء الاصطناعي عبر بيانات الأقمار الصناعية والتصوير الجوي والبيانات المتجهة.",
  "Start Validation": "ابدأ الفحص",
  "Explore Capabilities": "استكشف الإمكانات",
  "Change comparison": "مقارنة التغيّرات",
  "Same location, validated with AI": "الموقع نفسه، تم التحقق منه بالذكاء الاصطناعي",
  "Road Change Detected": "تم اكتشاف تغيّر في الطريق",
  "Building Mismatch": "عدم تطابق في المبنى",
  "New road segment": "مقطع طريق جديد",
  "New structure detected": "تم اكتشاف مبنى جديد",
  "Confidence": "الثقة",
  "Change Detection": "اكتشاف التغيّرات",
  "Spatial Validation": "الفحص المكاني",
  "AI Recommendations": "توصيات الذكاء الاصطناعي",
  "Identify real-world changes": "تعرّف على التغيّرات الفعلية",
  "Ensure map accuracy": "تحقق من دقة الخرائط",
  "Generate actionable insights": "أنشئ توصيات قابلة للتنفيذ",
  "Intelligence Dashboard": "لوحة المعلومات الذكية",
  "Interactive Map": "الخريطة التفاعلية",
  "Upload Data": "رفع البيانات",
  "Error Analysis": "تحليل الأخطاء",
  "Reports": "التقارير",
  "Saved Analyses": "التحليلات المحفوظة",
  "My Team": "فريقي",
  "Team Management": "إدارة الفريق",
  "Sign out": "تسجيل الخروج",
  "Personal information": "المعلومات الشخصية",
  "Dashboard": "لوحة التحكم",
  "Map": "الخريطة",
  "Analysis": "التحليل",
  "All systems online": "جميع الأنظمة تعمل",
  "Backend offline": "الخادم غير متصل",
  "Checking services": "جارٍ فحص الخدمات",
  "Turn Geospatial Data into": "حوّل البيانات الجغرافية إلى",
  "Reliable Decisions": "قرارات موثوقة",
  "Detect changes, analyze errors, and get AI-powered recommendations across vector and map imagery data.": "اكتشف التغيّرات، وحلّل الأخطاء، واحصل على توصيات ذكية للبيانات المتجهة وصور الخرائط.",
  "Open platform": "فتح المنصة",
  "Upload data": "رفع البيانات",
  "View capabilities": "عرض الإمكانات",
  "Detect errors": "اكتشاف الأخطاء",
  "Explore locations": "استكشاف المواقع",
  "Understand results": "فهم النتائج",
  "Export evidence": "تصدير النتائج",
  "Latest analysis": "آخر تحليل",
  "New analysis": "تحليل جديد",
  "Detected issues": "الأخطاء المكتشفة",
  "Priority findings": "النتائج ذات الأولوية",
  "View all": "عرض الكل",
  "No analysis selected": "لم يتم اختيار تحليل",
  "Upload vector data or a map image to populate the dashboard with live results.": "ارفع بيانات متجهة أو صورة خريطة لعرض نتائج التحليل في لوحة التحكم.",
  "Upload geospatial data": "رفع البيانات الجغرافية",
  "Upload vector data for PostGIS validation or a map image for visual element analysis.": "ارفع بيانات متجهة لفحصها عبر PostGIS أو صورة خريطة لتحليل عناصرها بصريًا.",
  "Vector data": "بيانات متجهة",
  "Map image": "صورة خريطة",
  "Layer type": "نوع الطبقة",
  "Roads": "الطرق",
  "Buildings": "المباني",
  "Select file": "اختيار الملف",
  "Choose a file to upload": "اختر ملفًا للرفع",
  "Start analysis": "بدء التحليل",
  "Analysis overview": "نظرة عامة على التحليل",
  "Result summary": "ملخص النتائج",
  "Total errors": "إجمالي الأخطاء",
  "High priority": "أولوية عالية",
  "Medium priority": "أولوية متوسطة",
  "Human review": "مراجعة بشرية",
  "Elements checked": "العناصر المفحوصة",
  "Elements present": "العناصر الموجودة",
  "Missing elements": "العناصر المفقودة",
  "Completion": "نسبة الاكتمال",
  "Spatial view": "العرض المكاني",
  "Original layer": "الطبقة الأصلية",
  "Errors": "الأخطاء",
  "Reset view": "إعادة ضبط العرض",
  "Search error or Feature ID": "ابحث عن خطأ أو معرّف عنصر",
  "All severities": "كل مستويات الخطورة",
  "All error types": "كل أنواع الأخطاء",
  "Clear": "مسح",
  "Errors and recommendations": "الأخطاء والتوصيات",
  "Review validation details and the recommended corrective actions.": "راجع تفاصيل الفحص والإجراءات التصحيحية المقترحة.",
  "Error": "الخطأ",
  "Feature": "العنصر",
  "Severity": "الخطورة",
  "Details": "التفاصيل",
  "Recommendation": "التوصية",
  "View on map": "عرض على الخريطة",
  "Selected on map": "محدد على الخريطة",
  "Full details": "التفاصيل الكاملة",
  "No errors detected": "لم يتم اكتشاف أخطاء",
  "Export report": "تصدير التقرير",
  "Download structured data or save this page as PDF.": "نزّل البيانات المنظمة أو احفظ الصفحة بصيغة PDF.",
  "Download JSON": "تنزيل JSON",
  "Save as PDF": "حفظ PDF",
  "Download PDF": "تنزيل PDF",
  "Generating PDF...": "جارٍ إنشاء PDF...",
  "Compliance score": "درجة الالتزام",
  "Internal data quality score": "درجة جودة البيانات الداخلية",
  "Internal image quality score": "درجة جودة الصورة الداخلية",
  "Review status": "حالة المراجعة",
  "New": "جديد",
  "Confirmed": "مؤكد",
  "Resolved": "تم الإصلاح",
  "False positive": "نتيجة خاطئة",
  "Add a review comment...": "أضف تعليق المراجعة...",
  "Save review": "حفظ المراجعة",
  "Saving...": "جارٍ الحفظ...",
  "Review saved": "تم حفظ المراجعة",
  "Vision analysis": "التحليل البصري",
  "Map elements": "عناصر الخريطة",
  "Present": "موجود",
  "Missing": "مفقود",
  "AI assistant": "المساعد الذكي",
  "Ask about this analysis": "اسأل عن هذا التحليل",
  "Send": "إرسال",
  "Ask a question about the detected errors...": "اسأل عن الأخطاء المكتشفة...",
  "Answers are grounded in the current validation run. Voice input and playback use your browser.": "تعتمد الإجابات على نتائج الفحص الحالي، ويستخدم الإدخال والنطق الصوتي المتصفح.",
  "Try: “Which errors should I fix first?”": "جرّب: «ما الأخطاء التي يجب أن أصلحها أولًا؟»",
  "Asking...": "جارٍ الإجابة...",
  "Listen": "استماع",
  "Download explanation": "تنزيل الشرح",
  "Download audio": "تنزيل الصوت",
  "Preparing audio...": "جارٍ تجهيز الصوت...",
  "Run information": "معلومات التشغيل",
  "File": "الملف",
  "Status": "الحالة",
  "Layer": "الطبقة",
  "Live overview of your latest geospatial quality analysis.": "نظرة مباشرة على أحدث نتائج جودة البيانات الجغرافية.",
  "Explore detected issues and their spatial context.": "استكشف الأخطاء المكتشفة وسياقها المكاني.",
  "Start a new vector or imagery validation workflow.": "ابدأ فحصًا جديدًا للبيانات المتجهة أو الصور.",
  "Filter, inspect, and resolve detected quality issues.": "صفِّ الأخطاء وافحصها واتخذ الإجراء المناسب لمعالجتها.",
  "Review the run summary and export audit-ready results.": "راجع ملخص التشغيل وصدّر النتائج الجاهزة للتقرير.",
  "Ask grounded questions about the current validation run.": "اطرح أسئلة مرتبطة بنتائج الفحص الحالي.",
  "Monitor your team members and their validation activity.": "تابع أعضاء فريقك وأنشطة الفحص الخاصة بهم.",
};

interface LanguageContextValue {
  language: Language;
  direction: "ltr" | "rtl";
  toggleLanguage: () => void;
  t: (text: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const direction = language === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
  }, [direction, language]);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    direction,
    toggleLanguage: () => setLanguage((current) => current === "en" ? "ar" : "en"),
    t: (text) => language === "ar" ? translations[text] ?? text : text,
  }), [direction, language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}
