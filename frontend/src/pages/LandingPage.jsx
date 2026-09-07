export default function LandingPage({onStart}){
  return (
    <div className="landing">
      <header className="landing-nav">
        <img src="/branding/meyaar-logo.png" className="landing-logo"/>

        <nav>
          <a>Home</a>
          <a>Platform</a>
          <a>About</a>
        </nav>

        <button className="button ghost" onClick={onStart}>
          Sign In
        </button>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">GEOSPATIAL QUALITY INTELLIGENCE</span>

          <h1>
            From Data to
            <span> Trusted Maps</span>
          </h1>

          <p>
            Agentic AI for Geospatial Data Quality & Standards Compliance
          </p>

          <button className="button primary" onClick={onStart}>
            Get Started
          </button>
        </div>

        <div className="hero-visual"/>
      </section>

      <section className="capabilities">
        <div>Automatic Data Understanding</div>
        <div>Standards-Aligned Validation</div>
        <div>AI Analysis & Recommendations</div>
        <div>Human-in-the-Loop</div>
        <div>Automated Reports</div>
      </section>

      <p className="slogan">عاير بياناتك على المعايير</p>
    </div>
  );
}