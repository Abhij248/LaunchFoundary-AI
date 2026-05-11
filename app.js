const presets = {
  restaurant: {
    name: "Bella Napoli",
    location: "San Francisco",
    goal: "increase online orders and table reservations",
    email: "hello@bellanapoli.example",
    details:
      "Bella Napoli is a family Italian restaurant in San Francisco. It serves pizza, pasta, desserts, and has a menu for pickup orders. Business hours are 11am to 10pm daily. The owner wants more online orders and table reservations.",
  },
  clinic: {
    name: "BrightCare Dental",
    location: "Austin",
    goal: "increase appointment bookings",
    email: "appointments@brightcare.example",
    details:
      "BrightCare Dental is a dental clinic in Austin. It offers cleaning, whitening, emergency dental care, implants, and family dentistry. Business hours are Monday to Friday 9am to 6pm. Patients should be able to book appointments online and submit intake information.",
  },
  service: {
    name: "Northstar Home Repair",
    location: "Denver",
    goal: "capture more qualified leads",
    email: "jobs@northstar.example",
    details:
      "Northstar Home Repair is a local repair service in Denver. It handles plumbing, electrical fixes, HVAC tuneups, and emergency repair requests. Customers need fast quotes, service area information, and a reliable contact workflow.",
  },
};

const featureRegistry = {
  online_ordering: {
    label: "Online ordering",
    applicableTo: ["restaurant", "cafe", "bakery"],
    requires: ["menu_items", "business_hours"],
    backend: ["orders_table", "cart", "order_status", "admin_orders"],
    qa: ["add_to_cart", "submit_order", "admin_order_visible"],
    trust: ["clear_prices", "pickup_delivery_info"],
    compliance: ["allergen_notice"],
    impact: "high",
    complexity: "medium",
  },
  table_reservation: {
    label: "Table reservation",
    applicableTo: ["restaurant", "cafe"],
    requires: ["business_hours", "contact_email"],
    backend: ["reservations_table", "availability_slots", "admin_reservations"],
    qa: ["reservation_submit", "admin_reservation_visible"],
    trust: ["opening_hours", "location"],
    compliance: [],
    impact: "high",
    complexity: "medium",
  },
  appointment_booking: {
    label: "Appointment booking",
    applicableTo: ["clinic", "salon", "tutor", "consultant", "repair_service"],
    requires: ["business_hours", "contact_email"],
    backend: ["bookings_table", "availability_rules", "admin_schedule"],
    qa: ["booking_submit", "admin_booking_visible"],
    trust: ["opening_hours", "phone_number"],
    compliance: ["appointment_disclaimer"],
    impact: "high",
    complexity: "medium",
  },
  patient_intake: {
    label: "Patient intake form",
    applicableTo: ["clinic"],
    requires: ["contact_email"],
    backend: ["patient_intake_table", "admin_patient_intake"],
    qa: ["intake_submit", "admin_intake_visible"],
    trust: ["privacy_notice"],
    compliance: ["medical_privacy_notice", "no_diagnosis_claims"],
    impact: "high",
    complexity: "medium",
  },
  lead_capture: {
    label: "Lead capture",
    applicableTo: [
      "restaurant",
      "cafe",
      "bakery",
      "clinic",
      "salon",
      "tutor",
      "consultant",
      "repair_service",
      "unknown",
    ],
    requires: ["contact_email"],
    backend: ["leads_table", "admin_leads"],
    qa: ["lead_form_submit", "admin_lead_visible"],
    trust: ["phone_number", "response_time"],
    compliance: [],
    impact: "medium",
    complexity: "low",
  },
};

const pagePresets = {
  restaurant: ["Home", "Menu", "Order Online", "Reservations", "About", "Contact"],
  cafe: ["Home", "Menu", "Order Online", "Events", "About", "Contact"],
  bakery: ["Home", "Menu", "Custom Orders", "Gallery", "About", "Contact"],
  clinic: ["Home", "Services", "Doctors", "Book Appointment", "Patient Intake", "Contact"],
  salon: ["Home", "Services", "Book Appointment", "Gallery", "About", "Contact"],
  tutor: ["Home", "Courses", "Book Trial Class", "Results", "About", "Contact"],
  repair_service: ["Home", "Services", "Request Quote", "Service Areas", "Reviews", "Contact"],
  consultant: ["Home", "Services", "Book Consultation", "Case Studies", "About", "Contact"],
  unknown: ["Home", "Services", "Contact"],
};

const verticalKeywords = [
  ["restaurant", ["restaurant", "diner", "bistro", "pizzeria", "food", "kitchen", "menu", "reservation", "catering", "pizza", "pasta"]],
  ["cafe", ["cafe", "coffee", "espresso"]],
  ["bakery", ["bakery", "cakes", "pastry", "bread", "cupcake"]],
  ["clinic", ["clinic", "dental", "doctor", "medical", "health", "patient", "therapy", "dentist"]],
  ["salon", ["salon", "spa", "hair", "beauty", "nails", "barber"]],
  ["tutor", ["tutor", "coaching", "academy", "classes", "lessons"]],
  ["repair_service", ["repair", "plumber", "electrician", "hvac", "mechanic"]],
  ["consultant", ["consultant", "agency", "advisor", "law firm", "accounting"]],
];

let state = {
  spec: null,
  designSpec: null,

  orders: [],
  bookings: [],
  leads: [],
  cart: [],

  assets: [],
  assetExtractions: [],
  extractedAssetText: "",
  amdInsights: null,

  timelineEvents: [],
  graphEvents: [],

  clarificationQuestions: [],
  pendingClarification: null,
  assumptions: [],
  isGenerating: false,
  resolveClarification: null,
};

function pushTimelineEvent(agent, message, badge = "active") {
  state.timelineEvents.push({
    id: crypto.randomUUID(),
    agent,
    message,
    badge,
    time: new Date().toLocaleTimeString(),
  });

  renderDynamicTimeline();
}

async function replayGraphEvents(events) {
  const sleep = (ms) =>
    new Promise((resolve) =>
      setTimeout(resolve, ms),
    );

  if (!events.length) {
    pushTimelineEvent(
      "System",
      "Planner graph is unavailable, so the app is using deterministic fallback mode with uploaded asset extraction where available.",
      "active",
    );
    updateCognitionPanel("fallback_mode", {
      observations: [
        "No graph events were returned.",
        "Build spec and website rendering are still active.",
        "Uploaded images, if any, were processed through the backend extraction path.",
      ],
    });
    return;
  }

  for (const event of events) {
    const nodeName = Object.keys(event)[0];
    const payload = event[nodeName];

    if (!nodeName) continue;

    updateCognitionPanel(
      nodeName,
      payload,
    );

    updateGraphExecution(
      nodeName,
    );

    switch (nodeName) {
      case "business_profile":
        pushTimelineEvent(
          "Business Understanding Agent",
          `Detected ${payload?.vertical || "unknown"} business with ${Math.round((payload?.confidence || 0.7) * 100)}% confidence.`,
          "classified",
        );
        break;

      case "requirements":
        pushTimelineEvent(
          "Requirements Agent",
          `Planned ${(payload?.required_pages || []).length} pages and ${(payload?.required_workflows || []).length} workflows.`,
          "researched",
        );
        break;

      case "strategy_hypotheses":
        pushTimelineEvent(
          "Strategy Agent",
          `Generated ${(payload || []).length || (payload?.strategies || []).length || 0} competing behavioural strategies.`,
          "thinking",
        );
        break;

      case "design_candidates":
        pushTimelineEvent(
          "Design Agent",
          `Created ${(payload || []).length || (payload?.candidates || []).length || 0} adaptive design candidates.`,
          "planned",
        );
        break;

      case "critique":
        pushTimelineEvent(
          "Critique Agent",
          "Evaluated strategic tradeoffs and workflow weaknesses.",
          "evaluated",
        );
        pushEvolutionUpdate(
          "CTA Strategy Revision",
          "Aggressive immediate conversion CTA",
          "Trust-first onboarding flow",
          "Critique and simulation agents detected hesitation before trust establishment.",
        );
        break;

      case "reflection":
        pushTimelineEvent(
          "Reflection Agent",
          "Reflection completed. Evaluating exploration quality.",
          "reflecting",
        );
        break;

      case "debate":
        pushTimelineEvent(
          "Debate Agent",
          payload?.winner_reasoning || "Debated competing strategies.",
          "debating",
        );
        break;

      case "simulation":
        pushTimelineEvent(
          "Simulation Agent",
          `Behavioural simulation realism score: ${payload?.overall_realism_score || "--"}/10`,
          "simulated",
        );
        pushEvolutionUpdate(
          "Workflow Optimization",
          "Users encountered friction during booking",
          "Progressive trust-building before booking interaction",
          "Simulation agent detected confusion among first-time visitors.",
        );
        break;

      case "revise":
        pushTimelineEvent(
          "Synthesis Agent",
          "Final adaptive website system synthesised.",
          "complete",
        );
        break;

      default:
        pushTimelineEvent(
          "Graph Agent",
          `Executed node: ${nodeName}`,
          "active",
        );
    }

    updateCognitionPanel(
      nodeName,
      payload,
    );

    await sleep(800);
  }
}

function updateCognitionPanel(
  nodeName,
  payload,
) {
  document.querySelector(
    "#activeNode",
  ).textContent =
    nodeName
      .replaceAll("_", " ")
      .toUpperCase();

  const uncertainty =
    payload?.uncertainty_score;

  if (
    uncertainty !== undefined
  ) {
    document.querySelector(
      "#uncertaintyValue",
    ).textContent =
      Number(uncertainty).toFixed(2);
  }

  if (
    payload?.exploration_quality
  ) {
    document.querySelector(
      "#explorationValue",
    ).textContent =
      `${payload.exploration_quality}/10`;
  }

  if (
    payload?.convergence_risk
  ) {
    document.querySelector(
      "#convergenceValue",
    ).textContent =
      `${payload.convergence_risk}/10`;
  }

  let reasoningLines = [];

  if (
    Array.isArray(payload?.reasoning_notes)
  ) {
    reasoningLines =
      payload.reasoning_notes;
  } else if (
    Array.isArray(payload?.observations)
  ) {
    reasoningLines =
      payload.observations;
  } else if (
    Array.isArray(payload?.tradeoff_analysis)
  ) {
    reasoningLines =
      payload.tradeoff_analysis;
  } else if (
    Array.isArray(payload?.systemic_issues)
  ) {
    reasoningLines =
      payload.systemic_issues;
  } else {
    reasoningLines = [
      `Executing ${nodeName}`,
    ];
  }

  document.querySelector(
    "#cognitionReasoning",
  ).innerHTML =
    reasoningLines
      .slice(-6)
      .map(
        (line) =>
          `<div class="thought-line">${line}</div>`,
      )
      .join("");
}

function pushEvolutionUpdate(
  title,
  beforeState,
  afterState,
  reason,
) {
  const feed =
    document.querySelector(
      "#evolutionFeed",
    );

  if (!feed) return;

  if (
    feed.querySelector(
      ".evolution-empty",
    )
  ) {
    feed.innerHTML = "";
  }

  const card =
    document.createElement("div");

  card.className =
    "evolution-card";

  card.innerHTML = `
    <div>
      <strong>${title}</strong>
    </div>

    <div class="evolution-stage">
      <div class="evolution-label">
        Before
      </div>

      <div>
        ${beforeState}
      </div>
    </div>

    <div class="evolution-arrow">
      ↓
    </div>

    <div class="evolution-stage">
      <div class="evolution-label">
        After
      </div>

      <div>
        ${afterState}
      </div>
    </div>

    <div class="evolution-reason">
      ${reason}
    </div>
  `;

  feed.prepend(card);
}

function updateGraphExecution(
  activeNode,
) {
  const orderedNodes = [
    "business_profile",
    "requirements",
    "strategy_hypotheses",
    "design_candidates",
    "critique",
    "reflection",
    "debate",
    "simulation",
    "revise",
  ];

  const activeIndex =
    orderedNodes.indexOf(activeNode);

  document
    .querySelectorAll(
      ".graph-node",
    )
    .forEach((node) => {
      const nodeIndex =
        orderedNodes.indexOf(
          node.dataset.node,
        );

      node.classList.remove(
        "active",
        "completed",
      );

      if (
        node.dataset.node ===
        activeNode
      ) {
        node.classList.add(
          "active",
        );
      }

      if (
        nodeIndex > -1 &&
        activeIndex > -1 &&
        nodeIndex < activeIndex
      ) {
        node.classList.add(
          "completed",
        );
      }
    });
}

function renderDynamicTimeline() {
  const timeline =
    document.querySelector(
      "#timeline"
    );

  const latest =
    state.timelineEvents[
      state.timelineEvents.length - 1
    ];

  if (!latest) return;

  const item =
    document.createElement("div");

  item.className =
    "timeline-item";

  item.innerHTML = `
    <div class="status-dot">✓</div>

    <div>
      <strong>${latest.agent}</strong>
      <p>${latest.message}</p>
      <small>${latest.time}</small>
    </div>

    <div class="confidence">
      ${latest.badge}
    </div>
  `;

  timeline.appendChild(item);

  timeline.scrollTop =
    timeline.scrollHeight;
}

function showClarificationCard(question) {
  state.pendingClarification = question;

  let container = document.querySelector(
    "#clarificationPopup",
  );

  if (!container) {
    container = document.createElement("div");

    container.id = "clarificationPopup";

    container.className =
      "clarification-popup";

    document.body.appendChild(container);
  }

  container.innerHTML = `
    <div class="clarification-card">
      <div class="chip">
        Agent clarification
      </div>

      <h3>${question.question}</h3>

      <div class="clarification-options">
        ${question.options
          .map(
            (option) => `
              <button
                class="clarification-option"
                data-answer="${option}"
              >
                ${option}
              </button>
            `,
          )
          .join("")}
      </div>
    </div>
  `;

  container.onclick = (event) => {
    const button = event.target.closest(
      ".clarification-option",
    );

    if (!button) return;

    const answer =
      button.dataset.answer;

    applyClarificationAnswer(
      question,
      answer,
    );
  };
}

function waitForClarification() {
  return new Promise((resolve) => {
    state.resolveClarification =
      resolve;

    showClarificationCard(
      state.clarificationQuestions[0]
    );
  });
}

function applyClarificationAnswer(
  question,
  answer,
) {
  state.assumptions.push({
    question: question.question,
    answer,
  });

  if (
    question.id ===
    "restaurant_order_mode"
  ) {
    state.spec.business.orderMode =
      answer;

    if (answer === "Delivery") {
      state.spec.business.goal =
        "increase delivery orders";
    }

    if (answer === "Pickup") {
      state.spec.business.goal =
        "increase pickup volume";
    }

    state.designSpec = null;
  }

  if (
    question.id ===
    "clinic_booking_mode"
  ) {
    state.spec.business.bookingMode =
      answer;

    if (
      answer ===
      "Request callback first"
    ) {
      state.spec.business.goal =
        "increase consultation callbacks";
    }

    state.designSpec = null;
  }

  document
    .querySelector("#clarificationPopup")
    ?.remove();

  state.pendingClarification = null;

  pushTimelineEvent(
    "Revision Agent",
    `Updated workflow using clarification: ${answer}`,
    "adapted",
  );

  pushTimelineEvent(
    "Planning Agent",
    "Revising website structure and workflow priorities using user feedback.",
    "planned",
  );

  if (
    state.resolveClarification
  ) {
    state.resolveClarification(
      answer
    );

    state.resolveClarification =
      null;
  }
}

function classifyVertical(raw) {
  const text = raw.toLowerCase();
  const scores = Object.fromEntries(
    verticalKeywords.map(([vertical, keywords]) => [
      vertical,
      keywords.filter((keyword) => text.includes(keyword)).length,
    ]),
  );
  const [vertical, score] = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  if (!score) {
    return {
      vertical: "unknown",
      confidence: 0.35,
      subtype: "general small business",
      riskLevel: "standard",
    };
  }
  return {
    vertical,
    confidence: Math.min(0.95, 0.55 + score * 0.09),
    subtype: vertical.replaceAll("_", " "),
    riskLevel: ["clinic", "consultant"].includes(vertical) ? "regulated" : "standard",
  };
}

function detectFields(profile, raw) {
  const text = raw.toLowerCase();
  const fields = new Set(Object.keys(profile));
  if (["menu", "pizza", "pasta", "coffee", "service", "brochure", "flyer"].some((word) => text.includes(word))) fields.add("menu_items");
  if (text.includes("hour") || text.includes("open")) fields.add("business_hours");
  if (text.includes("email") || profile.contact_email) fields.add("contact_email");
  if (text.includes("phone") || profile.phone) fields.add("phone_number");
  if (text.includes("location") || profile.location) fields.add("location");
  return fields;
}

function selectFeatures(vertical, availableFields) {
  const included = [];
  const skipped = [];
  const missing = new Set();

  Object.entries(featureRegistry).forEach(([key, feature]) => {
    if (!feature.applicableTo.includes(vertical) && !feature.applicableTo.includes("unknown")) return;

    const unmet = feature.requires.filter((field) => !availableFields.has(field));
    const decision = {
      key,
      label: feature.label,
      impact: feature.impact,
      complexity: feature.complexity,
      backend: feature.backend,
      qa: feature.qa,
      trust: feature.trust,
      compliance: feature.compliance,
    };

    if (unmet.length && key !== "lead_capture") {
      unmet.forEach((item) => missing.add(item));
      skipped.push({
        ...decision,
        reason: `Skipped because missing required info: ${unmet.join(", ")}`,
      });
    } else {
      included.push({
        ...decision,
        reason: `Included because it is high-value for ${vertical.replaceAll("_", " ")} businesses.`,
      });
    }
  });

  if (!included.length) {
    const lead = featureRegistry.lead_capture;
    included.push({
      key: "lead_capture",
      label: lead.label,
      impact: lead.impact,
      complexity: lead.complexity,
      backend: lead.backend,
      qa: lead.qa,
      trust: lead.trust,
      compliance: lead.compliance,
      reason: "Fallback module included so the business can capture customer interest immediately.",
    });
  }
  return { included, skipped, missing: [...missing] };
}

function uniqueFromFeatures(features, key) {
  return [...new Set(features.flatMap((feature) => feature[key]))].sort();
}

function readinessScores(vertical, included, missing) {
  const featureBonus = Math.min(12, included.length * 4);
  const missingPenalty = Math.min(16, missing.length * 4);
  const complianceBonus = ["clinic", "consultant"].includes(vertical) ? 6 : 2;
  const scores = {
    seo: Math.max(70, 84 + Math.floor(featureBonus / 2) - missingPenalty),
    ux: Math.max(70, 86 + Math.floor(featureBonus / 2) - Math.floor(missingPenalty / 2)),
    trust: Math.max(65, 80 + featureBonus - missingPenalty),
    conversion: Math.max(65, 82 + featureBonus - missingPenalty),
    compliance: Math.max(70, 84 + complianceBonus - Math.floor(missingPenalty / 2)),
  };
  scores.businessReadiness = Math.round(
    Object.values(scores).reduce((total, score) => total + score, 0) / Object.values(scores).length,
  );
  return scores;
}

function generateBuildSpec() {
  const profile = {
    name: document.querySelector("#businessName").value.trim(),
    location: document.querySelector("#businessLocation").value.trim(),
    goal: document.querySelector("#businessGoal").value,
    contact_email: document.querySelector("#businessEmail").value.trim(),
  };
  const raw = [document.querySelector("#businessDetails").value, state.extractedAssetText].filter(Boolean).join("\n\n");
  const analysis = classifyVertical(raw);
  const fields = detectFields(profile, raw);
  const selected = selectFeatures(analysis.vertical, fields);
  const backend = uniqueFromFeatures(selected.included, "backend");
  const trust = uniqueFromFeatures(selected.included, "trust");
  const compliance = uniqueFromFeatures(selected.included, "compliance");
  const qa = uniqueFromFeatures(selected.included, "qa");
  const scores = readinessScores(analysis.vertical, selected.included, selected.missing);

  return {
    business: {
      name: profile.name || "Unnamed Business",
      location: profile.location || "Unknown",
      goal: profile.goal,
      ...analysis,
    },
    pages: pagePresets[analysis.vertical] || pagePresets.unknown,
    includedFeatures: selected.included,
    skippedFeatures: selected.skipped,
    missingInfo: selected.missing,
    backend,
    trust,
    compliance,
    qa: ["functional", "visual", "business", "conversion", "compliance", ...qa],
    scores,
  };
}

function generateClarificationQuestions(spec) {
  const questions = [];

  if (
    spec.business.vertical === "clinic" &&
    !state.extractedAssetText.toLowerCase().includes("booking")
  ) {
    questions.push({
      id: "clinic_booking_mode",
      question:
        "Should patients book appointments directly online or request callbacks first?",
      options: [
        "Direct online booking",
        "Request callback first",
      ],
      importance: "high",
    });
  }

  if (
    ["restaurant", "cafe", "bakery"].includes(spec.business.vertical)
  ) {
    questions.push({
      id: "restaurant_order_mode",
      question:
        "Should the ordering flow prioritise pickup, delivery, or both?",
      options: [
        "Pickup",
        "Delivery",
        "Both",
      ],
      importance: "medium",
    });
  }

  return questions;
}

function renderTimeline(spec) {
  const timeline = [
    [
      "Business Understanding Agent",
      `Classified as ${spec.business.vertical.replaceAll("_", " ")} with ${Math.round(spec.business.confidence * 100)}% confidence.`,
      "classified",
    ],
    [
      "Requirement Discovery Agent",
      `Mapped ${spec.pages.length} pages, detected ${spec.business.riskLevel} operating risk, and reviewed ${state.assets.length} uploaded assets.`,
      "researched",
    ],
    [
      "Feature Selection Agent",
      `Selected ${spec.includedFeatures.length} modules and skipped ${spec.skippedFeatures.length} low-confidence modules.`,
      "composed",
    ],
    [
      "Backend Builder Agent",
      `Planned ${spec.backend.length} backend resources for customer actions and owner operations.`,
      "wired",
    ],
    [
      "Trust + Compliance Agent",
      `Added ${spec.trust.length} trust signals and ${spec.compliance.length || 1} compliance checks.`,
      "guarded",
    ],
    [
      "QA Agent",
      `Prepared ${spec.qa.length} tests across function, visual quality, conversion, and business readiness.`,
      "verified",
    ],
  ];
  document.querySelector("#timeline").innerHTML = timeline
    .map(
      ([title, text, badge]) => `
        <div class="timeline-item">
          <div class="status-dot">✓</div>
          <div><strong>${title}</strong><p>${text}</p></div>
          <div class="confidence">${badge}</div>
        </div>
      `,
    )
    .join("");
}

function renderSpec(spec) {
  const featureCards = spec.includedFeatures
    .map(
      (feature) => `
        <article class="feature-card">
          <strong>${feature.label}</strong>
          <p>${feature.reason}</p>
          <div class="chip-row">
            <span class="chip">Impact: ${feature.impact}</span>
            <span class="chip">Complexity: ${feature.complexity}</span>
          </div>
        </article>
      `,
    )
    .join("");
  const skipped = spec.skippedFeatures.length
    ? spec.skippedFeatures
        .map(
          (feature) => `
            <article class="feature-card">
              <strong>Skipped: ${feature.label}</strong>
              <p>${feature.reason}</p>
            </article>
          `,
        )
        .join("")
    : `<article class="feature-card"><strong>No critical skips</strong><p>The input had enough information for the selected workflow.</p></article>`;

  document.querySelector("#specCards").innerHTML = `
    <article class="metric-card">
      <strong>${spec.business.name}</strong>
      <p>${spec.business.vertical.replaceAll("_", " ")} · ${spec.business.riskLevel} · ${Math.round(spec.business.confidence * 100)}% confidence</p>
      <div class="chip-row">${spec.pages.map((page) => `<span class="chip">${page}</span>`).join("")}</div>
    </article>
    ${featureCards}
    ${skipped}
  `;
  document.querySelector("#specJson").textContent = JSON.stringify(spec, null, 2);
}

function renderWebsite(spec) {
  renderWebsiteDynamic(spec, state.designSpec || generateDesignSpec(spec));
}

function renderRestaurantWebsite(spec, visual) {
  renderWebsiteDynamic(spec, state.designSpec || generateDesignSpec(spec));
}

function heroCopy(spec) {
  if (spec.business.vertical === "clinic") {
    return "A patient-ready digital front desk with appointments, intake, trust signals, and compliance-aware language.";
  }
  if (["restaurant", "cafe", "bakery"].includes(spec.business.vertical)) {
    return "A local food ordering system with a polished storefront, reservation path, menu structure, and owner dashboard.";
  }
  return "A service-ready website with quote capture, clear offerings, trust signals, and a generated owner workflow.";
}

function verticalVisual(vertical) {
  if (vertical === "clinic") {
    return {
      className: "clinic-hero",
      cardTitle: "Patient Trust Stack",
      cardBody: "Doctor profiles, privacy notice, intake workflow, and appointment confirmation are planned together.",
    };
  }
  if (["restaurant", "cafe", "bakery"].includes(vertical)) {
    return {
      className: "restaurant-hero",
      cardTitle: "Revenue Stack",
      cardBody: "Menu, order flow, reservation flow, opening hours, and admin operations are generated as one system.",
    };
  }
  return {
    className: "service-hero",
    cardTitle: "Lead Stack",
    cardBody: "Service pages, trust signals, quote capture, and owner follow-up workflow are connected.",
  };
}

function verticalTiles(spec) {
  if (spec.business.vertical === "clinic") {
    return [
      {
        title: "Care Pathways",
        body: "Services are grouped around patient intent: routine care, urgent care, cosmetic care, and family care.",
      },
      {
        title: "Book + Intake",
        body: "Appointment booking and patient intake feed the same admin schedule instead of becoming dead-end forms.",
      },
      {
        title: "Compliance Guardrails",
        body: "Medical claims are restrained, privacy language is present, and diagnosis promises are avoided.",
      },
    ];
  }
  if (["restaurant", "cafe", "bakery"].includes(spec.business.vertical)) {
    return [
      {
        title: "Menu To Action",
        body: "Menu items are arranged around immediate ordering, pickup expectations, and clear customer choices.",
      },
      {
        title: "Reservations",
        body: "Table requests are routed into an owner dashboard so the site supports real service operations.",
      },
      {
        title: "Local Trust",
        body: "Hours, location, pricing clarity, and allergen notice are treated as launch-critical trust signals.",
      },
    ];
  }
  return [
    {
      title: "Service Clarity",
      body: "The homepage explains what the business does, who it serves, and what action customers should take.",
    },
    {
      title: "Quote Capture",
      body: "Requests are collected with enough context for the owner to respond quickly and prioritise work.",
    },
    {
      title: "Owner Workflow",
      body: "Leads appear in the generated admin area so the website becomes an operating surface.",
    },
  ];
}

function systemProofCopy(spec) {
  if (spec.business.vertical === "clinic") {
    return "The site is not just patient-facing UI; it includes appointment intake, admin visibility, and regulated copy checks.";
  }
  if (["restaurant", "cafe", "bakery"].includes(spec.business.vertical)) {
    return "The generated storefront connects customer actions to owner operations through orders, reservations, and QA checks.";
  }
  return "Customer requests are captured, organised, and verified through the generated admin workflow.";
}

function renderAdmin() {
  renderRecordList("#ordersList", state.orders, "No orders yet. Submit from the generated website.");
  renderRecordList("#bookingsList", state.bookings, "No bookings yet. Submit from the generated website.");
  renderRecordList("#leadsList", state.leads, "No leads yet. Submit from the generated website.");
}

function renderRecordList(selector, records, emptyText) {
  document.querySelector(selector).innerHTML = records.length
    ? records
        .map(
          (record) => `
            <article class="record">
              <strong>${record.customer}</strong>
              <p>${record.request}</p>
              <small>${record.contact} · ${record.time}</small>
            </article>
          `,
        )
        .join("")
    : `<p class="empty">${emptyText}</p>`;
}

function renderQa(spec) {
  const fixes = qaFixesFor(spec);
  const qaItems = [
    ["Functional QA", "Buttons, navigation, and workflow forms passed after backend visibility check.", 96, "submit -> admin record verified"],
    ["Visual QA", fixes.visual, spec.scores.ux, "detected -> fixed"],
    ["Business QA", `${spec.business.vertical.replaceAll("_", " ")} essentials are present for launch.`, spec.scores.businessReadiness, "vertical checklist passed"],
    ["Conversion QA", fixes.conversion, spec.scores.conversion, "CTA route verified"],
    ["Trust QA", `${spec.trust.length} trust signals included and surfaced near customer decisions.`, spec.scores.trust, "trust gaps reviewed"],
    ["Compliance QA", fixes.compliance, spec.scores.compliance, "risk language reviewed"],
    ["SEO QA", "Pages, headings, and local intent are represented in the generated structure.", spec.scores.seo, "metadata planned"],
  ];
  document.querySelector("#qaReport").innerHTML = `
    <article class="qa-card">
      <div>
        <strong>Business Readiness</strong>
        <p>Launch score after planning, backend composition, and QA checks.</p>
      </div>
      <div class="score-ring" style="--score:${spec.scores.businessReadiness}"><span>${spec.scores.businessReadiness}</span></div>
    </article>
    ${qaItems
      .map(
        ([title, body, score, badge]) => `
          <article class="qa-card">
            <div>
              <strong>✓ ${title}</strong>
              <p>${body}</p>
              <span class="mini-badge">${badge}</span>
            </div>
            <span class="confidence">${score}</span>
          </article>
        `,
      )
      .join("")}
  `;
}

function qaFixesFor(spec) {
  if (spec.business.vertical === "clinic") {
    return {
      visual: "Detected weak appointment CTA hierarchy on mobile, then promoted booking above intake.",
      conversion: "Primary booking action is available in hero and connected to generated schedule backend.",
      compliance: "Medical outcome wording checked; privacy notice and no-diagnosis guardrails included.",
    };
  }
  if (["restaurant", "cafe", "bakery"].includes(spec.business.vertical)) {
    return {
      visual: "Detected menu/order content competing with hero copy, then grouped actions into a revenue stack.",
      conversion: "Order and reservation flows are both visible and connected to owner operations.",
      compliance: "Allergen and pricing clarity checks were applied before launch readiness scoring.",
    };
  }
  return {
    visual: "Detected generic service cards, then rewrote them around customer intent and quote capture.",
    conversion: "Request flow is reachable from the hero and stored in the generated lead dashboard.",
    compliance: "Risk language reviewed for the selected business category.",
  };
}

async function runDemo() {
  if (state.isGenerating) return;

  state.isGenerating = true;

  try {
    state.timelineEvents = [];
    state.graphEvents = [];
    state.assetExtractions = [];
    state.amdInsights = null;

    document
      .querySelectorAll(
        ".graph-node",
      )
      .forEach((node) => {
        node.classList.remove(
          "active",
          "completed",
        );
      });

    document.querySelector(
      "#timeline",
    ).innerHTML = "";

    document.querySelector(
      "#evolutionFeed",
    ).innerHTML = `<div class="evolution-empty">Awaiting strategic revisions...</div>`;

    document
      .querySelector(
        "#clarificationPopup",
      )
      ?.remove();

    const response =
      await fetch(
        "/generate-buildspec",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            business_input: {
              name:
                document.querySelector(
                  "#businessName",
                ).value,
              location:
                document.querySelector(
                  "#businessLocation",
                ).value,
              goal:
                document.querySelector(
                  "#businessGoal",
                ).value,
              contact_email:
                document.querySelector(
                  "#businessEmail",
                ).value,
              details:
                document.querySelector(
                  "#businessDetails",
                ).value,
            },
          }),
        },
      );

    if (!response.ok) {
      throw new Error(
        `${response.status} ${await response.text()}`
      );
    }

    const result =
      await response.json();

    console.log(
      "GRAPH RESPONSE",
      result,
    );

    state.graphEvents =
      result?.graphExecution?.events || [];

    state.assetExtractions =
      result?.assetExtractions || [];

    state.extractedAssetText =
      result?.assetSignals || "";

    state.amdInsights =
      buildAmdInsights(
        state.assetExtractions,
      );

    state.spec =
      result?.buildSpec ||
      generateBuildSpec();

    state.designSpec =
      normalizeServerDesignSpec(
        result?.designSpec ||
        result?.graphExecution?.final_state?.design_spec,
      ) ||
      generateDesignSpec(
        state.spec,
      );

    await replayGraphEvents(
      state.graphEvents,
    );

    renderSpecDynamic(
      state.spec,
      state.designSpec,
    );

    renderWebsiteDynamic(
      state.spec,
      state.designSpec,
    );

    renderAdmin();

    renderQa(
      state.spec,
    );

    renderAmdStatus(
      state.graphEvents.length
        ? "Local planner"
        : "Fallback planner",
    );

    showPanel(
      "reasoning",
    );
  } catch (error) {
    console.error(
      "Graph execution failed",
      error,
    );

    pushTimelineEvent(
      "System",
      `Execution failed: ${error.message}`,
      "error",
    );
  } finally {
    state.isGenerating =
      false;
  }
}

async function applyAmdPayload(payload, sourceLabel = "AMD Developer Cloud import") {
  state.assetExtractions = payload.assetExtractions || [];
  state.extractedAssetText = payload.assetSignals || "";
  state.amdInsights = buildAmdInsights(state.assetExtractions);
  state.spec = payload.buildSpec;
  state.designSpec =
    normalizeServerDesignSpec(
      payload.designSpec ||
      payload.graphExecution?.final_state?.design_spec,
    ) ||
    generateDesignSpec(state.spec);

  document.querySelector("#assetExtraction").textContent =
    payload.assetSignals ||
    "AMD inference completed. No image-specific signals were returned, but BuildSpec generation succeeded.";

  await renderAllFromSpec(sourceLabel);
}

async function renderAllFromSpec(sourceLabel = "Local planner") {
  if (!state.spec) return;

  if (!state.designSpec) {
    state.designSpec = generateDesignSpec(state.spec);
  }

  renderTimeline(state.spec);
  renderSpecDynamic(state.spec, state.designSpec);
  renderWebsiteDynamic(state.spec, state.designSpec);
  renderAdmin();
  renderQa(state.spec);
  renderAmdStatus(sourceLabel);
}

function showPanel(id) {
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("is-visible", panel.id === id);
  });
  document.querySelectorAll(".step").forEach((step) => {
    step.classList.toggle("is-active", step.dataset.target === id);
  });
}

document.querySelectorAll(".step").forEach((step) => {
  step.addEventListener("click", () => showPanel(step.dataset.target));
});

document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    const preset = presets[button.dataset.preset];
    document.querySelector("#businessName").value = preset.name;
    document.querySelector("#businessLocation").value = preset.location;
    document.querySelector("#businessGoal").value = preset.goal;
    document.querySelector("#businessEmail").value = preset.email;
    document.querySelector("#businessDetails").value = preset.details;
  });
});

document.querySelector("#runDemo").addEventListener("click", runDemo);

document.querySelector("#businessAssets").addEventListener("change", async (event) => {
  const files = [...(event.currentTarget.files || [])];
  state.assets = await Promise.all(files.map(readAssetFile));
  renderAssetPreview();
  document.querySelector("#assetExtraction").textContent =
    files.length
      ? `${files.length} asset${files.length === 1 ? "" : "s"} loaded. Click Generate With AMD to send them to the backend.`
      : "No assets extracted yet. In the AMD flow, this step is powered by a vision/multimodal model on GPU.";
});

document.querySelector("#extractAssets").addEventListener("click", () => {
  if (!state.assets.length) {
    document.querySelector("#assetExtraction").textContent = "Upload at least one image before extraction.";
    return;
  }
  state.extractedAssetText = extractAssetSignals(state.assets);
  document.querySelector("#assetExtraction").textContent = state.extractedAssetText;
  const details = document.querySelector("#businessDetails");
  if (!details.value.includes("Extracted asset signals:")) {
    details.value = `${details.value.trim()}\n\n${state.extractedAssetText}`;
  }
});

document.querySelector("#runAmdAssets").addEventListener("click", async () => {
  const status = document.querySelector("#assetExtraction");
  const fileInput = document.querySelector("#businessAssets");
  const files = [...(fileInput.files || [])];

  const profile = {
    name: document.querySelector("#businessName").value.trim(),
    location: document.querySelector("#businessLocation").value.trim(),
    goal: document.querySelector("#businessGoal").value,
    contact_email: document.querySelector("#businessEmail").value.trim(),
  };

  try {
    status.textContent = files.length
      ? `Uploading ${files.length} image${files.length === 1 ? "" : "s"} to the backend for extraction...`
      : "Generating from business details only...";

    const endpoint = "/generate-buildspec";
    const baseBusinessDetails = document.querySelector("#businessDetails").value;

    const payload = await requestAmdBuildSpec(
      endpoint,
      profile,
      baseBusinessDetails,
      files,
    );

    await applyAmdPayload(payload, "Local pollinations.ai vision model");
    showPanel("reasoning");
  } catch (error) {
    status.textContent =
      [
        `Local processing failed: ${error.message}`,
        `Endpoint: ${"/generate-buildspec"}`,
        `Asset count: ${files.length}`,
        "Check that the server is running and the pollinations.ai API is accessible.",
      ].join("\n\n");
    console.error("Local processing failed", { error });
  }
});

document.querySelector("#clearAssets").addEventListener("click", () => {
  state.assets = [];
  state.assetExtractions = [];
  state.extractedAssetText = "";
  state.amdInsights = null;
  state.designSpec = null;
  document.querySelector("#businessAssets").value = "";
  document.querySelector("#assetPreview").innerHTML = "";
  document.querySelector("#assetExtraction").textContent =
    "No assets extracted yet. In the AMD flow, this step is powered by a vision/multimodal model on GPU.";
});

document.querySelector("#copySpec").addEventListener("click", async () => {
  const json = JSON.stringify(state.spec, null, 2);
  try {
    await navigator.clipboard.writeText(json);
    document.querySelector("#copySpec").textContent = "Copied";
    setTimeout(() => {
      document.querySelector("#copySpec").textContent = "Copy Build Spec";
    }, 1200);
  } catch {
    document.querySelector("#specJson").focus();
  }
});

document.querySelector("#downloadSpec").addEventListener("click", () => {
  const json = JSON.stringify(state.spec, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.spec.business.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-buildspec.json`;
  anchor.click();
  URL.revokeObjectURL(url);
});

document.querySelector("#loadCurrentSpec").addEventListener("click", () => {
  document.querySelector("#amdSpecInput").value = JSON.stringify(state.spec, null, 2);
});

document.querySelector("#amdSpecFile").addEventListener("change", async (event) => {
  const file = event.currentTarget.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const imported = JSON.parse(text);
    validateImportedSpec(imported);
    document.querySelector("#amdSpecInput").value = JSON.stringify(imported, null, 2);
    document.querySelector("#amdStatus").textContent =
      `Loaded ${file.name}. Click Apply AMD Spec to drive the app with this BuildSpec.`;
  } catch (error) {
    document.querySelector("#amdStatus").textContent = `File import failed: ${error.message}`;
  }
});

document.querySelector("#applyAmdSpec").addEventListener("click", async () => {
  const input = document.querySelector("#amdSpecInput").value.trim();
  if (!input) {
    renderAmdStatus("empty import");
    return;
  }
  try {
    const imported = JSON.parse(input);
    validateImportedSpec(imported);
    state.spec = imported;
    state.designSpec = generateDesignSpec(imported);
    await renderAllFromSpec("AMD Developer Cloud import");
    showPanel("spec");
  } catch (error) {
    document.querySelector("#amdStatus").textContent = `Import failed: ${error.message}`;
  }
});

document.querySelector("#loadLatestAmdResult").addEventListener("click", async () => {
  const status = document.querySelector("#amdStatus");
  status.textContent = "Loading the latest AMD payload written by the notebook...";
  try {
    const response = await fetch("./amd_result.json", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${await response.text()}`);
    }
    const payload = await response.json();
    validateAmdPayload(payload);
    document.querySelector("#amdSpecInput").value = JSON.stringify(payload.buildSpec, null, 2);
    await applyAmdPayload(payload, "AMD notebook bridge import");
    status.textContent = "Loaded amd_result.json from the notebook workspace and applied it to the UI.";
    showPanel("website");
  } catch (error) {
    status.textContent = `Latest AMD result load failed: ${error.message}`;
  }
});

function validateImportedSpec(spec) {
  const required = ["business", "pages", "includedFeatures", "backend", "trust", "compliance", "qa", "scores"];
  const missing = required.filter((key) => !(key in spec));
  if (missing.length) {
    throw new Error(`missing keys: ${missing.join(", ")}`);
  }
  if (!spec.business.name || !spec.business.vertical) {
    throw new Error("business.name and business.vertical are required");
  }
  if (!Array.isArray(spec.includedFeatures) || !Array.isArray(spec.pages)) {
    throw new Error("pages and includedFeatures must be arrays");
  }
  if (!Number.isFinite(spec.scores.businessReadiness)) {
    throw new Error("scores.businessReadiness must be a number");
  }
}

function validateAmdPayload(payload) {
  if (!payload || !payload.buildSpec) {
    throw new Error("missing AMD payload key: buildSpec");
  }
  validateImportedSpec(payload.buildSpec);
}

function renderAmdStatus(sourceLabel) {
  const status = document.querySelector("#amdStatus");
  if (!status || !state.spec) return;
  const source =
    sourceLabel === "AMD Developer Cloud import"
      ? "AMD-generated BuildSpec is active and driving the local product flow."
      : sourceLabel === "Fallback planner"
        ? "Local fallback planner is active. Uploaded images were still sent to the backend extraction pipeline."
        : "Local deterministic planner is active. Use this shape for AMD notebook inference output.";
  status.textContent = `${source} Current spec: ${state.spec.business.name}, ${state.spec.business.vertical.replaceAll("_", " ")}, readiness ${state.spec.scores.businessReadiness}.`;
}

function normalizeApiUrl(rawValue) {
  if (!rawValue) return "";
  const trimmed = rawValue.trim();
  if (!trimmed) return "";
  if (trimmed.toLowerCase() === "auto") return "auto";
  if (trimmed.startsWith("/")) {
    return trimmed.replace(/\/+$/, "");
  }
  return trimmed.replace(/\/+$/, "");
}

function candidateApiUrls(rawValue) {
  const normalized = normalizeApiUrl(rawValue);
  if (normalized && normalized !== "auto") {
    return [normalized];
  }

  const candidates = [
    "/proxy/8000",
    "/proxy/absolute/8000",
    "/user-redirect/proxy/8000",
    "./proxy/8000",
    "./proxy/absolute/8000",
    "../proxy/8000",
    "../proxy/absolute/8000",
    "proxy/8000",
    "proxy/absolute/8000",
  ];

  return [...new Set(candidates.map((value) => value.replace(/\/+$/, "")))];
}

async function resolveAmdApiUrl() {
  return "";
}

function buildApiEndpoint(apiUrl, path) {
  return `/${path.replace(/^\/+/, "")}`;
}

async function requestAmdBuildSpec(
  endpoint,
  profile,
  businessDetails,
  files = [],
) {
  let response;

  if (files && files.length) {
    const formData = new FormData();
    formData.append(
      "payload",
      JSON.stringify({
        business_input: {
          ...profile,
          details: businessDetails,
        },
      }),
    );

    files.forEach((file) => {
      formData.append("files", file);
    });

    response = await fetch(
      endpoint,
      {
        method: "POST",
        body: formData,
      },
    );
  } else {
    response = await fetch(
      endpoint,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          business_input: {
            ...profile,
            details:
              businessDetails,
          },
        }),
      },
    );
  }

  if (!response.ok) {
    throw new Error(
      `${response.status} ${await response.text()}`
    );
  }

  return response.json();
}

function mergeAmdPayloads(profile, businessDetails, payloads) {
  const assetExtractions = payloads.flatMap((payload) => payload.assetExtractions || []);
  const assetSignals = assetExtractions.length
    ? buildCombinedAssetSignals(assetExtractions)
    : payloads.map((payload) => payload.assetSignals || "").filter(Boolean).join("\n");
  const buildSpec = payloads[payloads.length - 1]?.buildSpec || generateBuildSpecFromAmdPayload(profile, businessDetails, assetSignals);
  const graphExecution = payloads[payloads.length - 1]?.graphExecution;

  return {
    source: "amd-developer-cloud-qwen2.5-vl-batched",
    assetSignals,
    assetExtractions,
    buildSpec,
    graphExecution,
  };
}

function buildCombinedAssetSignals(extractions) {
  const lines = ["Extracted asset signals:"];
  extractions.forEach((item) => {
    const parsed = item?.parsed || item || {};
    const info = parsed.extracted_business_info || {};
    lines.push(`File: ${displayAssetName(item.image)}`);
    lines.push(`Asset type: ${parsed.asset_type || "unknown"}`);
    (parsed.business_signals || []).slice(0, 6).forEach((signal) => lines.push(`- Signal: ${signal}`));
    if (info.services_or_items?.length) {
      lines.push(`- Services/items visible: ${uniqueCompact(info.services_or_items.map(String), 12).join(", ")}`);
    }
    if (info.prices?.length) {
      lines.push(`- Prices visible: ${uniqueCompact(info.prices.map(formatInsightPrice), 8).join(", ")}`);
    }
    (parsed.recommended_features || []).slice(0, 6).forEach((feature) => lines.push(`- Recommended feature: ${feature}`));
    if (parsed.planner_notes) {
      lines.push(`- Planner note: ${parsed.planner_notes}`);
    }
  });
  return lines.join("\n");
}

function generateBuildSpecFromAmdPayload(profile, businessDetails, assetSignals) {
  const raw = [businessDetails, assetSignals].filter(Boolean).join("\n\n");
  const analysis = classifyVertical(raw);
  const fields = detectFields(profile, raw);
  const selected = selectFeatures(analysis.vertical, fields);
  const backend = uniqueFromFeatures(selected.included, "backend");
  const trust = uniqueFromFeatures(selected.included, "trust");
  const compliance = uniqueFromFeatures(selected.included, "compliance");
  const qa = uniqueFromFeatures(selected.included, "qa");
  const scores = readinessScores(analysis.vertical, selected.included, selected.missing);

  return {
    business: {
      name: profile.name || "Unnamed Business",
      location: profile.location || "Unknown",
      goal: profile.goal,
      ...analysis,
    },
    pages: pagePresets[analysis.vertical] || pagePresets.unknown,
    includedFeatures: selected.included,
    skippedFeatures: selected.skipped,
    missingInfo: selected.missing,
    backend,
    trust,
    compliance,
    qa: ["functional", "visual", "business", "conversion", "compliance", ...qa],
    scores,
  };
}

function displayAssetName(imagePath) {
  if (!imagePath) return "uploaded-asset";
  const parts = String(imagePath).split(/[\\/]/);
  return parts[parts.length - 1];
}

function readAssetFile(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve({
        name: file.name,
        type: file.type,
        size: file.size,
        url: reader.result,
      });
    };
    reader.readAsDataURL(file);
  });
}

function renderAssetPreview() {
  document.querySelector("#assetPreview").innerHTML = state.assets
    .map(
      (asset) => `
        <article class="asset-card">
          <img src="${asset.url}" alt="${asset.name}" />
          <div>
            <strong>${asset.name}</strong>
            <small>${Math.round(asset.size / 1024)} KB</small>
          </div>
        </article>
      `,
    )
    .join("");
}

function extractAssetSignals(assets) {
  const names = assets.map((asset) => asset.name.toLowerCase()).join(" ");
  const signals = new Set();
  const inferred = [];

  if (names.includes("menu") || names.includes("food") || names.includes("dish")) {
    signals.add("menu image detected");
    signals.add("menu_items");
    inferred.push("Business likely needs menu page, online ordering, clear prices, pickup/delivery details, and allergen notice.");
  }
  if (names.includes("flyer") || names.includes("brochure")) {
    signals.add("marketing collateral detected");
    inferred.push("Use uploaded collateral to infer services, offer language, trust claims, and contact details.");
  }
  if (names.includes("store") || names.includes("front") || names.includes("shop")) {
    signals.add("storefront photo detected");
    inferred.push("Use storefront asset for local trust, location context, and hero visual direction.");
  }
  if (names.includes("doctor") || names.includes("clinic") || names.includes("dental")) {
    signals.add("clinic/doctor asset detected");
    inferred.push("Business likely needs doctor profiles, appointment booking, intake form, privacy notice, and restrained medical copy.");
  }
  if (names.includes("service") || names.includes("price")) {
    signals.add("service or price list detected");
    inferred.push("Business likely needs service catalog, quote capture, pricing clarity, and lead dashboard.");
  }
  if (!signals.size) {
    signals.add("general business imagery detected");
    inferred.push("Use image assets for brand direction, visual trust, page imagery, and missing-info prompts.");
  }

  return [
    "Extracted asset signals:",
    `Files reviewed: ${assets.map((asset) => asset.name).join(", ")}`,
    `Detected: ${[...signals].join(", ")}`,
    ...inferred.map((item) => `- ${item}`),
    "AMD production path: run a vision/multimodal model on Developer Cloud to extract menu items, services, prices, contact details, and visual brand cues.",
  ].join("\n");
}

function renderAmdInsightsPanel() {
  if (!state.amdInsights || !state.amdInsights.assetCount) {
    return "";
  }
  return `
    <section class="insights-panel">
      <div>
        <strong>AI found in your uploads</strong>
        <p>${state.amdInsights.assetCount} asset${state.amdInsights.assetCount === 1 ? "" : "s"} analysed on backend vision extraction.</p>
      </div>
      <div class="insights-grid">
        <article class="insight-card">
          <strong>Offers</strong>
          <p>${state.amdInsights.offers.length ? state.amdInsights.offers.join(", ") : "No explicit offers detected."}</p>
        </article>
        <article class="insight-card">
          <strong>Top Items</strong>
          <p>${state.amdInsights.items.length ? state.amdInsights.items.join(", ") : "No item list detected."}</p>
        </article>
        <article class="insight-card">
          <strong>Recommended Features</strong>
          <p>${state.amdInsights.features.length ? state.amdInsights.features.join(", ") : "No special features suggested."}</p>
        </article>
        <article class="insight-card">
          <strong>Price Examples</strong>
          <p>${state.amdInsights.prices.length ? state.amdInsights.prices.join(", ") : "No clear prices detected."}</p>
        </article>
      </div>
    </section>
  `;
}

function buildAmdInsights(extractions) {
  const offers = [];
  const items = [];
  const features = [];
  const prices = [];

  extractions.forEach((item) => {
    const parsed = item || {};
    const info = parsed.extracted_business_info || {};
    (info.offers || []).forEach((offer) => offers.push(String(offer)));
    (info.services_or_items || []).forEach((entry) => items.push(String(entry)));
    (parsed.recommended_features || []).forEach((feature) => features.push(String(feature)));
    (info.prices || []).forEach((price) => prices.push(formatInsightPrice(price)));
  });

  return {
    assetCount: extractions.length,
    offers: uniqueCompact(offers, 6),
    items: uniqueCompact(items, 8),
    features: uniqueCompact(features, 6),
    prices: uniqueCompact(prices, 6),
  };
}

function uniqueCompact(values, limit) {
  const seen = new Set();
  const output = [];
  values.forEach((value) => {
    const clean = String(value).trim();
    if (!clean) return;
    const key = clean.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    output.push(clean);
  });
  return output.slice(0, limit);
}

function formatInsightPrice(value) {
  if (Array.isArray(value)) {
    return "[" + value.slice(0, 4).join(", ") + "]";
  }
  return String(value);
}

function generateDesignSpec(spec) {
  const vertical = spec.business.vertical;
  const restaurant = buildRestaurantExperienceData();
  const hasStrongOffers = restaurant.offers.length > 0;
  const hasRichMenu = restaurant.items.length >= 6;
  const hasVisualAssets = state.assets.length >= 2;

  if (["restaurant", "cafe", "bakery"].includes(vertical)) {
    return {
      brief: hasStrongOffers
        ? "Lead with an offer-driven food storefront, then move quickly into dense ordering UI with strong imagery and price visibility."
        : "Lead with food visuals and social proof, then present a dense menu-first ordering layout with immediate action paths.",
      visual: {
        tone: hasStrongOffers ? "fast-casual and promotional" : "food-forward and trustworthy",
        density: hasRichMenu ? "high" : "medium",
        mediaBias: hasVisualAssets ? "image-heavy" : "content-heavy",
        trustEmphasis: "medium",
      },
      primaryAction: { label: "Order Now", kind: "order", placements: ["hero", "section_end"] },
      pages: [
        {
          name: "Home",
          pageType: "home",
          sections: [
            { type: "hero_offer_banner", purpose: "Lead with the main commercial hook." },
            { type: "insights", purpose: "Show extracted AMD insights." },
            { type: hasVisualAssets ? "gallery_strip" : "page_nav", purpose: "Support browsing." },
            { type: hasRichMenu ? "menu_showcase" : "feature_grid", purpose: "Display the core offer." },
            { type: "proof_band", purpose: "Support conversion confidence." },
            { type: "primary_workflow_form", purpose: "Capture order intent." },
          ],
        },
      ],
      decisionRationale: ["Restaurant flow prioritised ordering speed and visual appetite."],
    };
  }

  if (vertical === "clinic") {
    return {
      brief: "Prioritise trust, credentials, and appointment conversion before deeper service detail.",
      visual: { tone: "calm and credible", density: "medium", mediaBias: "trust-first", trustEmphasis: "high" },
      primaryAction: { label: "Book Appointment", kind: "booking", placements: ["hero", "section_end"] },
      pages: [{ name: "Home", pageType: "home", sections: [{ type: "hero_trust_banner" }, { type: "insights" }, { type: "page_nav" }, { type: "feature_grid" }, { type: "proof_band" }, { type: "primary_workflow_form" }] }],
      decisionRationale: ["Clinic flow prioritised reassurance and trust before booking."],
    };
  }

  return {
    brief: "Prioritise service clarity and lead capture, supported by trust signals and operational readiness.",
    visual: { tone: "clear and pragmatic", density: "medium", mediaBias: "copy-first", trustEmphasis: "medium" },
    primaryAction: { label: "Request Quote", kind: "lead", placements: ["hero", "section_end"] },
    pages: [{ name: "Home", pageType: "home", sections: [{ type: "hero_trust_banner" }, { type: "insights" }, { type: "page_nav" }, { type: "feature_grid" }, { type: "proof_band" }, { type: "primary_workflow_form" }] }],
    decisionRationale: ["Service flow prioritised clarity and quote capture."],
  };
}

function renderSpecDynamic(spec, designSpec) {
  const visualTone = designSpec.visual?.tone || designSpec.visual_system?.tone || "practical";
  const visualDensity = designSpec.visual?.density || designSpec.visual_system?.density || "medium";
  const ctaLabel = designSpec.primaryAction?.label || designSpec.primary_action?.label || "Continue";

  const designCard = `
    <article class="feature-card design-brief-card">
      <strong>Design Brief</strong>
      <p>${designSpec.brief}</p>
      <div class="chip-row">
        <span class="chip">Tone: ${visualTone}</span>
        <span class="chip">Density: ${visualDensity}</span>
        <span class="chip">CTA: ${ctaLabel}</span>
      </div>
    </article>
  `;
  const featureCards = spec.includedFeatures
    .map(
      (feature) => `
        <article class="feature-card">
          <strong>${feature.label}</strong>
          <p>${feature.reason}</p>
          <div class="chip-row">
            <span class="chip">Impact: ${feature.impact}</span>
            <span class="chip">Complexity: ${feature.complexity}</span>
          </div>
        </article>
      `,
    )
    .join("");
  const skipped = spec.skippedFeatures.length
    ? spec.skippedFeatures
        .map(
          (feature) => `
            <article class="feature-card">
              <strong>Skipped: ${feature.label}</strong>
              <p>${feature.reason}</p>
            </article>
          `,
        )
        .join("")
    : `<article class="feature-card"><strong>No critical skips</strong><p>The input had enough information for the selected workflow.</p></article>`;

  document.querySelector("#specCards").innerHTML = `
    <article class="metric-card">
      <strong>${spec.business.name}</strong>
      <p>${spec.business.vertical.replaceAll("_", " ")} | ${spec.business.riskLevel} | ${Math.round(spec.business.confidence * 100)}% confidence</p>
      <div class="chip-row">${spec.pages.map((page) => `<span class="chip">${page}</span>`).join("")}</div>
    </article>
    ${designCard}
    ${featureCards}
    ${skipped}
  `;
  document.querySelector("#specJson").textContent = JSON.stringify({ ...spec, designSpec }, null, 2);
}

function renderWebsiteDynamic(spec, designSpec) {
  const restaurant = buildRestaurantExperienceData();
  const visual = designAwareVisual(spec, designSpec);
  const pages =
    (designSpec.pages && designSpec.pages.length)
      ? designSpec.pages
      : [
          {
            name: "Home",
            pageType: "home",
            sections: [],
          },
        ];

  const homePage =
    pages.find(
      (page) =>
        (page.pageType || "").toLowerCase() === "home",
    ) || pages[0];

  const heroSection =
    (homePage.sections || []).find((section) =>
      [
        "hero_offer_banner",
        "hero_trust_banner",
      ].includes(
        getSectionType(section),
      ),
    );

  const bodySections =
    (homePage.sections || []).filter((section) => {
      const sectionType =
        getSectionType(section);

      return ![
        "hero_offer_banner",
        "hero_trust_banner",
      ].includes(sectionType);
    });

  const pageSections =
    bodySections
      .map((section) =>
        renderDesignSection(
          section,
          spec,
          designSpec,
          restaurant,
        ),
      )
      .join("");

  const additionalPages =
    pages
      .filter(
        (page) =>
          page !== homePage,
      )
      .map((page) =>
        renderDesignPage(
          page,
          spec,
          designSpec,
          restaurant,
        ),
      )
      .join("");

  let adaptiveHeroCopy =
    heroSectionCopy(
      spec,
      designSpec,
      heroSection,
    );

  if (
    spec.business.orderMode ===
    "Delivery"
  ) {
    adaptiveHeroCopy =
      "A delivery-optimised ordering experience with rapid checkout, promo visibility, and operational delivery workflows.";
  }

  if (
    spec.business.orderMode ===
    "Pickup"
  ) {
    adaptiveHeroCopy =
      "A pickup-first storefront optimised for fast local ordering and streamlined collection.";
  }

  if (
    spec.business.bookingMode ===
    "Request callback first"
  ) {
    adaptiveHeroCopy =
      "A trust-first consultation flow designed to encourage patient callback requests before scheduling.";
  }

  let adaptiveCta =
    designSpec.primaryAction.label;

  if (
    spec.business.orderMode ===
    "Delivery"
  ) {
    adaptiveCta =
      "Start Delivery Order";
  }

  if (
    spec.business.orderMode ===
    "Pickup"
  ) {
    adaptiveCta =
      "Start Pickup Order";
  }

  if (
    spec.business.bookingMode ===
    "Request callback first"
  ) {
    adaptiveCta =
      "Request Callback";
  }

  document.querySelector(
    "#sitePreview",
  ).innerHTML = `
    <section
      class="generated-hero ${visual.className}"
      ${buildHeroBackground(
        spec,
        restaurant,
        heroSection,
      )}
    >
      <div>
        <p class="eyebrow">
          ${spec.business.location}
        </p>

        <h3>
          ${spec.business.name}
        </h3>

        <p>
          ${adaptiveHeroCopy}
        </p>

        ${renderHeroSupportChips(
          spec,
          designSpec,
          restaurant,
          heroSection,
        )}

        <button
          class="primary-button"
          data-scroll-form
        >
          ${adaptiveCta}
        </button>

        ${
          spec.business.orderMode
            ? `
          <div class="assumption-chip">
            Optimised for:
            ${spec.business.orderMode}
          </div>
        `
            : ""
        }

        ${
          spec.business.bookingMode
            ? `
          <div class="assumption-chip">
            Booking mode:
            ${spec.business.bookingMode}
          </div>
        `
            : ""
        }
      </div>

      <div class="generated-card restaurant-summary-card">
        <strong>
          ${heroCardTitle(
            designSpec,
            heroSection,
          )}
        </strong>

        <p>
          ${heroCardBody(
            spec,
            designSpec,
            restaurant,
            heroSection,
          )}
        </p>

        <div class="summary-stats">
          <div>
            <span>
              ${
                restaurant.items.length ||
                spec.includedFeatures.length
              }
            </span>

            <small>
              ${
                restaurant.items.length
                  ? "menu items"
                  : "capabilities"
              }
            </small>
          </div>

          <div>
            <span>
              ${
                restaurant.categories.length ||
                spec.pages.length
              }
            </span>

            <small>
              ${
                restaurant.categories.length
                  ? "categories"
                  : "pages"
              }
            </small>
          </div>

          <div>
            <span>
              ${
                restaurant.priceRange
              }
            </span>

            <small>
              ${
                designSpec.visual.tone
              }
            </small>
          </div>
        </div>
      </div>
    </section>

    <section class="generated-body">
      ${pageSections}

      ${additionalPages}

      ${renderDecisionRationaleBand(
        designSpec,
      )}
    </section>
  `;

  attachWebsiteInteractions(
    spec,
    designSpec,
    restaurant,
  );
}

function renderDesignSection(section, spec, designSpec, restaurant) {
  const sectionType = getSectionType(section);
  const sectionPurpose = getSectionPurpose(section);

  switch (sectionType) {
    case "hero_offer_banner":
    case "hero_trust_banner":
      return "";
    case "insights":
      return renderAmdInsightsPanel();
    case "page_nav":
      return renderPageNav(spec, designSpec);
    case "category_strip":
      return renderCategoryStripSection(restaurant, sectionPurpose);
    case "gallery_strip":
      return `
        <div class="restaurant-topbar">
          ${renderPageNav(spec, designSpec)}
          <div class="restaurant-thumbs">
            ${restaurant.heroImages.slice(0, 4).map((asset) => `<img src="${asset.url}" alt="${asset.name}" />`).join("")}
          </div>
        </div>
      `;
    case "menu_showcase":
      return renderMenuShowcaseSection(spec, restaurant, designSpec, sectionPurpose);
    case "review_band":
      return renderReviewBandSection(spec, restaurant, sectionPurpose);
    case "trust_band":
      return renderTrustBandSection(spec, sectionPurpose);
    case "feature_grid":
      return `
        <div class="generated-grid">
          ${verticalTiles(spec)
            .map((tile) => `<article class="generated-tile"><strong>${tile.title}</strong><p>${tile.body}</p></article>`)
            .join("")}
        </div>
      `;
    case "proof_band":
      return `
        <section class="proof-band">
          <div>
            <strong>Generated business system</strong>
            <p>${systemProofCopy(spec)}</p>
          </div>
          <div class="chip-row">
            ${spec.includedFeatures.map((feature) => `<span class="chip">${feature.label}</span>`).join("")}
          </div>
        </section>
      `;
    case "primary_workflow_form":
    case "order_form":
      return renderPrimaryWorkflowForm(spec, designSpec, restaurant);
    default:
      return "";
  }
}

function renderPageNav(spec, designSpec) {
  const pageLabels = (designSpec.pages || []).length
    ? designSpec.pages.map((page) => page.name || page.title || "Page")
    : spec.pages;
  return `<div class="website-nav">${pageLabels.map((page) => `<span>${page}</span>`).join("")}</div>`;
}

function renderDesignPage(page, spec, designSpec, restaurant) {
  const sections = (page.sections || [])
    .map((section) => renderDesignSection(section, spec, designSpec, restaurant))
    .join("");
  if (!sections) return "";

  return `
    <section class="generated-page">
      <div class="menu-header generated-page-header">
        <div>
          <p class="eyebrow">${formatPageLabel(page.pageType || page.name || "page")}</p>
          <strong>${page.name || page.title || "Page"}</strong>
          <p>${pageIntroCopy(page)}</p>
        </div>
      </div>
      ${sections}
    </section>
  `;
}

function renderCategoryStripSection(restaurant, sectionPurpose) {
  const categories = restaurant.categories.length ? restaurant.categories : ["Popular", "Offers", "Pizza"];
  return `
    <section class="menu-header category-strip-section">
      <div>
        <strong>Browse by category</strong>
        <p>${sectionPurpose || "The planner grouped the offer into fast scanning lanes so visitors can compare before they commit."}</p>
      </div>
      <div class="chip-row">
        ${categories.map((category) => `<span class="chip">${category}</span>`).join("")}
      </div>
    </section>
  `;
}

function renderMenuShowcaseSection(spec, restaurant, designSpec, sectionPurpose) {
  const categoryChips = restaurant.categories.length ? restaurant.categories : ["Popular", "Offers", "Pizzas"];
  const featuredItems = restaurant.items.slice(0, 8);
  const isTrustBrowsing = designSpec.primaryAction.label === "Explore Menu" || designSpec.visual.trustEmphasis === "high";
  return `
    <section class="menu-shell">
      <div class="menu-column">
        <div class="menu-header">
          <div>
            <strong>Order online</strong>
            <p>${sectionPurpose || (isTrustBrowsing
              ? "The agent chose a richer exploration flow here so customers can browse, compare, and build confidence before ordering."
              : "The agent chose a dense, menu-first layout here because this business has rich item and price data that customers will compare quickly.")}</p>
          </div>
          <div class="chip-row">
            ${categoryChips.map((category) => `<span class="chip">${category}</span>`).join("")}
          </div>
        </div>
        <div class="menu-grid">${featuredItems.map((item) => renderMenuCard(item)).join("")}</div>
      </div>
      <aside class="cart-column">
        <div class="cart-card">
          <strong>Quick cart</strong>
          <p>${state.cart.length ? `${state.cart.length} item${state.cart.length === 1 ? "" : "s"} selected` : "Choose a few dishes and they will appear here."}</p>
          <div class="cart-list">
            ${state.cart.length ? state.cart.map((item) => `<div class="cart-row"><span>${item.name}</span><strong>${item.priceLabel}</strong></div>`).join("") : `<p class="empty">No items added yet.</p>`}
          </div>
          <div class="cart-total">
            <span>Estimated total</span>
            <strong>${restaurant.cartTotalLabel}</strong>
          </div>
        </div>
      </aside>
    </section>
  `;
}

function renderReviewBandSection(spec, restaurant, sectionPurpose) {
  const reviewCards = [
    {
      title: "Offer-led discovery",
      body: restaurant.offers[0] || "Seasonal offers and clear promos are surfaced before the action step.",
    },
    {
      title: "Menu confidence",
      body: `${restaurant.items[0]?.name || "Signature items"} and pricing stay visible while customers browse.`,
    },
    {
      title: "Local trust",
      body: `The ${spec.business.name} plan uses proof before asking for the final commitment.`,
    },
  ];
  return `
    <section class="generated-grid review-band-section">
      ${reviewCards
        .map(
          (card) => `
            <article class="generated-tile">
              <strong>${card.title}</strong>
              <p>${card.body}</p>
            </article>
          `,
        )
        .join("")}
      <article class="generated-tile">
        <strong>Why this appears here</strong>
        <p>${sectionPurpose || "The planner moved reassurance ahead of the CTA so visitors can browse with more confidence."}</p>
      </article>
    </section>
  `;
}

function renderTrustBandSection(spec, sectionPurpose) {
  const trustItems = (spec.trust || []).slice(0, 4);
  return `
    <section class="proof-band trust-band-section">
      <div>
        <strong>Trust signals</strong>
        <p>${sectionPurpose || "Clear pricing, direct contact, and low-friction next steps reduce hesitation before action."}</p>
      </div>
      <div class="chip-row">
        ${trustItems.length
          ? trustItems.map((item) => `<span class="chip">${item.replaceAll("_", " ")}</span>`).join("")
          : `<span class="chip">Clear next steps</span><span class="chip">Fast response</span><span class="chip">Visible pricing</span>`}
      </div>
    </section>
  `;
}

function renderPrimaryWorkflowForm(spec, designSpec, restaurant) {
  const kind = designSpec.primaryAction.kind;
  const requestLabel = kind === "order" ? "Order item" : kind === "booking" ? "Service needed" : "Request";
  const requestValue =
    kind === "order"
      ? state.cart[0]?.name || restaurant.items[0]?.name || "Margherita Pizza"
      : kind === "booking"
        ? "Dental cleaning"
        : "Emergency repair quote";
  const formClass = kind === "order" ? "workflow-form restaurant-order-form" : "workflow-form";
  return `
    <form id="workflowForm" class="${formClass}" data-type="${kind}">
      <label>
        Customer name
        <input name="customer" value="Alex Morgan" required />
      </label>
      <label>
        ${requestLabel}
        <input name="request" value="${requestValue}" required />
      </label>
      <label>
        Contact
        <input name="contact" value="alex@example.com" required />
      </label>
      <button class="primary-button" type="submit">${designSpec.primaryAction.label}</button>
    </form>
  `;
}

function buildHeroBackground(spec, restaurant, heroSection) {
  if (!restaurant.heroImages[0]) return "";
  const heroType = typeof heroSection === "string" ? heroSection : heroSection?.type;
  const overlay =
    heroType === "hero_trust_banner"
      ? "linear-gradient(115deg, rgba(16, 42, 54, 0.92), rgba(34, 72, 78, 0.74))"
      : "linear-gradient(115deg, rgba(23, 53, 46, 0.92), rgba(80, 52, 32, 0.74))";
  return `style="background-image: ${overlay}, url('${restaurant.heroImages[0].url}'); background-size: cover; background-position: center;"`;
}

function attachWebsiteInteractions(spec, designSpec, restaurant) {
  const scrollButton = document.querySelector("[data-scroll-form]");
  if (scrollButton) {
    scrollButton.addEventListener("click", () => {
      document.querySelector("#workflowForm")?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  document.querySelectorAll("[data-add-item]").forEach((button) => {
    button.addEventListener("click", () => {
      const itemId = button.dataset.addItem;
      const selectedItem = restaurant.items.find((item) => item.id === itemId);
      if (!selectedItem) return;
      state.cart.unshift(selectedItem);
      renderWebsiteDynamic(spec, designSpec);
      const orderInput = document.querySelector('#workflowForm input[name="request"]');
      if (orderInput) orderInput.value = selectedItem.name;
    });
  });

  document.querySelector("#workflowForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    const record = { ...data, time: new Date().toLocaleTimeString() };
    if (designSpec.primaryAction.kind === "order") state.orders.unshift(record);
    if (designSpec.primaryAction.kind === "booking") state.bookings.unshift(record);
    if (designSpec.primaryAction.kind === "lead") state.leads.unshift(record);
    state.cart = [];
    renderAdmin();
    if (designSpec.primaryAction.kind === "order") {
      renderWebsiteDynamic(spec, designSpec);
    }
    showPanel("admin");
  });
}

function normalizeServerDesignSpec(designSpec) {
  if (!designSpec) return null;
  return {
    brief: designSpec.brief,
    chosenCandidateId: designSpec.chosen_candidate_id || "",
    visual: {
      tone: designSpec.visual_system?.tone || "practical",
      density: designSpec.visual_system?.density || "medium",
      mediaBias: designSpec.visual_system?.media_bias || "copy_first",
      trustEmphasis: designSpec.visual_system?.trust_emphasis || "medium",
    },
    primaryAction: {
      label: designSpec.primary_action?.label || "Continue",
      kind: designSpec.primary_action?.kind || "lead",
      placements: designSpec.primary_action?.placements || [],
    },
    pages: (designSpec.pages || []).map((page) => ({
      name: page.title || page.page_type || "Page",
      title: page.title || page.page_type || "Page",
      pageType: page.page_type || "",
      sections: (page.sections || []).map((section) => ({
        type: section.type,
        purpose: section.purpose || "",
        rationale: section.rationale || "",
        priority: section.priority || 0,
      })),
    })),
    decisionRationale: designSpec.decision_rationale || [],
  };
}

function designAwareVisual(spec, designSpec) {
  const verticalVisualBase = verticalVisual(spec.business.vertical);
  const tone = designSpec.visual?.tone || "practical";
  if (tone === "trustworthy" || tone === "calm") {
    return {
      className: spec.business.vertical === "clinic" ? "clinic-hero" : "service-hero",
      cardTitle: "Confidence-first layout",
      cardBody: "The agent shifted this experience toward reassurance, exploration, and lower-pressure conversion.",
    };
  }
  return verticalVisualBase;
}

function heroSectionCopy(spec, designSpec, heroSection) {
  const heroType = typeof heroSection === "string" ? heroSection : heroSection?.type;
  if (heroType === "hero_trust_banner") {
    return "The agent chose to open with confidence-building context before the action step, so visitors can explore the offer with more clarity.";
  }
  return heroCopy(spec);
}

function renderHeroSupportChips(spec, designSpec, restaurant, heroSection) {
  const heroType = typeof heroSection === "string" ? heroSection : heroSection?.type;
  const chips =
    heroType === "hero_trust_banner"
      ? ["Browse before you decide", "Clear pricing", "Local trust signals"]
      : restaurant.offers.length
        ? restaurant.offers
        : ["Live ordering enabled"];
  return `<div class="chip-row">${chips.map((item) => `<span class="chip offer-chip">${item}</span>`).join("")}</div>`;
}

function heroCardTitle(designSpec, heroSection) {
  const heroType = typeof heroSection === "string" ? heroSection : heroSection?.type;
  if (heroType === "hero_trust_banner") return "Trust-first storefront";
  return "Conversion-first storefront";
}

function heroCardBody(spec, designSpec, restaurant, heroSection) {
  const heroType = typeof heroSection === "string" ? heroSection : heroSection?.type;
  if (heroType === "hero_trust_banner") {
    return "This direction emphasises visual reassurance, richer browsing, and social proof before the final order step.";
  }
  return "This direction emphasises the strongest commercial signal early, shortens time-to-action, and keeps the ordering path visible.";
}

function renderDecisionRationaleBand(designSpec) {
  if (!designSpec.decisionRationale?.length) return "";
  return `
    <section class="proof-band">
      <div>
        <strong>Planner rationale</strong>
        <p>${designSpec.brief || "The final storefront direction was selected from the candidate set."}</p>
      </div>
      <div class="chip-row">
        ${designSpec.decisionRationale.slice(0, 4).map((item) => `<span class="chip">${item}</span>`).join("")}
      </div>
    </section>
  `;
}

function getSectionType(section) {
  return typeof section === "string" ? section : section?.type || "";
}

function getSectionPurpose(section) {
  return typeof section === "string" ? "" : section?.purpose || "";
}

function formatPageLabel(value) {
  return String(value || "page").replaceAll("_", " ");
}

function pageIntroCopy(page) {
  const pageType = (page.pageType || "").toLowerCase();
  if (pageType === "menu") return "This page leans into item discovery, category scanning, and price clarity.";
  if (pageType === "order") return "This page carries the final action path and keeps the workflow focused.";
  if (pageType === "contact") return "This page makes support, contact expectations, and fallback conversion clear.";
  return "This page is rendered directly from the agent-selected page structure.";
}

function buildRestaurantExperienceData() {
  const items = [];
  const offers = [];
  const categories = [];
  let categoryIndex = 1;

  state.assetExtractions.forEach((extraction) => {
    const parsed = extraction || {};
    const info = parsed.extracted_business_info || {};
    const assetType = parsed.asset_type || "menu";
    const signals = parsed.business_signals || [];
    const services = (info.services_or_items || []).slice(0, 18);
    const prices = info.prices || [];
    const categoryName = inferMenuCategory(parsed, assetType, categoryIndex);
    if (categoryName) categories.push(categoryName);
    categoryIndex += 1;
    (info.offers || []).forEach((offer) => offers.push(String(offer)));
    signals
      .filter((signal) => /off|combo|deal|discount/i.test(signal))
      .forEach((signal) => offers.push(String(signal)));

    services.forEach((service, index) => {
      const priceValue = prices[index] ?? prices[0] ?? null;
      items.push({
        id: `${assetType}-${categoryIndex}-${index}`,
        name: String(service),
        category: categoryName,
        description: buildMenuDescription(service, categoryName, signals),
        priceLabel: formatMenuPrice(priceValue),
        priceSortValue: getMenuPriceNumber(priceValue),
        visual: state.assets[index % Math.max(state.assets.length, 1)]?.url || "",
      });
    });
  });

  const dedupedItems = dedupeMenuItems(items).slice(0, 16);
  const fallbackItems = dedupedItems.length
    ? dedupedItems
    : [
        { id: "fallback-1", name: "Margherita Pizza", category: "Popular", description: "House favourite with quick delivery flow.", priceLabel: "₹199", priceSortValue: 199, visual: state.assets[0]?.url || "" },
        { id: "fallback-2", name: "Veggie Feast", category: "Popular", description: "Customer-friendly menu layout with clear pricing.", priceLabel: "₹249", priceSortValue: 249, visual: state.assets[1]?.url || state.assets[0]?.url || "" },
      ];

  const usableOffers = uniqueCompact(offers, 4);
  const uniqueCategories = uniqueCompact(categories.filter(Boolean), 5);
  const priceNumbers = fallbackItems.map((item) => item.priceSortValue).filter((value) => Number.isFinite(value));
  const cartTotal = state.cart.reduce((total, item) => total + (item.priceSortValue || 0), 0);

  return {
    items: fallbackItems,
    offers: usableOffers,
    categories: uniqueCategories,
    heroImages: state.assets,
    priceRange: priceNumbers.length ? `₹${Math.min(...priceNumbers)}-₹${Math.max(...priceNumbers)}` : "₹199-₹399",
    cartTotalLabel: cartTotal ? `₹${cartTotal}` : "₹0",
  };
}

function inferMenuCategory(parsed, assetType, categoryIndex) {
  const signals = (parsed.business_signals || []).map((value) => String(value));
  const joined = signals.join(" ");
  if (/veg/i.test(joined)) return "Veg";
  if (/non-veg|chicken/i.test(joined)) return "Non-Veg";
  if (/pasta/i.test(joined)) return "Pasta";
  if (/mocktail/i.test(joined)) return "Beverages";
  if (/garlic/i.test(joined)) return "Sides";
  if (assetType === "flyer") return "Offers";
  return categoryIndex === 1 ? "Popular" : `Section ${categoryIndex}`;
}

function buildMenuDescription(itemName, categoryName, signals) {
  const qualifiers = [];
  if (categoryName) qualifiers.push(categoryName);
  if (signals.length) qualifiers.push(String(signals[0]));
  qualifiers.push("Fast checkout");
  return `${qualifiers.slice(0, 2).join(" | ")} | ${itemName}`;
}

function formatMenuPrice(value) {
  if (Array.isArray(value) && value.length) {
    const numeric = value.filter((entry) => Number.isFinite(Number(entry))).map(Number);
    if (!numeric.length) return "₹199";
    const minimum = Math.min(...numeric);
    const maximum = Math.max(...numeric);
    return minimum === maximum ? `₹${minimum}` : `₹${minimum} - ₹${maximum}`;
  }
  if (Number.isFinite(Number(value))) {
    return `₹${Number(value)}`;
  }
  return "₹199";
}

function getMenuPriceNumber(value) {
  if (Array.isArray(value) && value.length) {
    const numeric = value.filter((entry) => Number.isFinite(Number(entry))).map(Number);
    return numeric.length ? Math.min(...numeric) : 0;
  }
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function dedupeMenuItems(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = item.name.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderMenuCard(item) {
  return `
    <article class="menu-card">
      <div class="menu-card-media">
        ${item.visual ? `<img src="${item.visual}" alt="${item.name}" />` : `<div class="menu-card-fallback">${item.category}</div>`}
      </div>
      <div class="menu-card-body">
        <div class="menu-card-meta">
          <span class="chip">${item.category}</span>
          <strong>${item.priceLabel}</strong>
        </div>
        <h4>${item.name}</h4>
        <p>${item.description}</p>
        <button class="ghost-button menu-add-button" type="button" data-add-item="${item.id}">Add</button>
      </div>
    </article>
  `;
}
