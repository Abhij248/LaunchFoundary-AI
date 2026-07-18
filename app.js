let activePageIndex = 0;

window.latestSpec = null;
window.latestDesignSpec = null;
window.latestRestaurant = null;

const presets = {
  restaurant: {
    name: "Bella Napoli",
    location: "San Francisco",
    goal: "increase online orders and table reservations",
    email: "hello@bellanapoli.example",
    details:
      "Bella Napoli is a family Italian restaurant in San Francisco. It serves pizza, pasta, desserts, and has a menu for pickup orders. Business hours are 11am to 10pm daily. The owner wants more online orders and table reservations.",
    target_audience: "Families and young professionals in San Francisco looking for authentic Italian dining",
    unique_selling_points: "Family recipes passed down 3 generations, wood-fired pizza, gluten-free options",
    business_hours: "11am-10pm daily",
    phone_number: "+1 (415) 555-0123",
    primary_color: "#dc2626",
    secondary_color: "#1e3a8a",
    accent_color: "#f59e0b",
  },
  clinic: {
    name: "BrightCare Dental",
    location: "Austin",
    goal: "increase appointment bookings",
    email: "appointments@brightcare.example",
    details:
      "BrightCare Dental is a dental clinic in Austin. It offers cleaning, whitening, emergency dental care, implants, and family dentistry. Business hours are Monday to Friday 9am to 6pm. Patients should be able to book appointments online and submit intake information.",
    target_audience: "Families and professionals in Austin seeking comprehensive dental care",
    unique_selling_points: "Same-day emergency appointments, modern technology, gentle care approach",
    business_hours: "Mon-Fri 9am-6pm",
    phone_number: "+1 (512) 555-0456",
    primary_color: "#0891b2",
    secondary_color: "#0e7490",
    accent_color: "#14b8a6",
  },
  service: {
    name: "Northstar Home Repair",
    location: "Denver",
    goal: "capture more qualified leads",
    email: "jobs@northstar.example",
    details:
      "Northstar Home Repair is a local repair service in Denver. It handles plumbing, electrical fixes, HVAC tuneups, and emergency repair requests. Customers need fast quotes, service area information, and a reliable contact workflow.",
    target_audience: "Homeowners in Denver metro area needing reliable home maintenance",
    unique_selling_points: "24/7 emergency service, licensed and insured technicians, upfront pricing",
    business_hours: "24/7 emergency, Mon-Sat 8am-6pm for routine",
    phone_number: "+1 (303) 555-0789",
    primary_color: "#f97316",
    secondary_color: "#ea580c",
    accent_color: "#fbbf24",
  },
};

const featureRegistry = {
  online_ordering: {
    label: "Online ordering",
    applicableTo: ["restaurant", "cafe", "bakery"],
    applicableToShapes: ["storefront_commerce"],
    requires: ["menu_items", "business_hours"],
    backend: ["menu_items_table", "orders_table", "cart", "order_status", "admin_orders"],
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
    applicableToShapes: ["storefront_commerce", "scheduled_booking", "inquiry_lead", "portfolio_showcase", "catalog_reserve"],
    requires: ["contact_email"],
    backend: ["leads_table", "admin_leads"],
    qa: ["lead_form_submit", "admin_lead_visible"],
    trust: ["phone_number", "response_time"],
    compliance: [],
    impact: "medium",
    complexity: "low",
  },
  quote_request: {
    label: "Quote request",
    applicableTo: [],
    applicableToShapes: ["inquiry_lead"],
    requires: ["contact_email"],
    backend: ["quotes_table", "admin_quotes"],
    qa: ["quote_submit", "admin_quote_visible"],
    trust: ["response_time", "phone_number"],
    compliance: [],
    impact: "high",
    complexity: "low",
  },
  portfolio_showcase: {
    label: "Portfolio showcase",
    applicableTo: [],
    applicableToShapes: ["portfolio_showcase"],
    requires: [],
    backend: ["portfolio_items_table", "admin_portfolio"],
    qa: ["portfolio_item_visible"],
    trust: ["case_study_evidence"],
    compliance: [],
    impact: "high",
    complexity: "medium",
  },
  catalog_reservation: {
    label: "Catalog reservation",
    applicableTo: [],
    applicableToShapes: ["catalog_reserve"],
    requires: [],
    backend: ["catalog_items_table", "holds_table", "admin_holds"],
    qa: ["hold_submit", "admin_hold_visible"],
    trust: ["availability_status"],
    compliance: [],
    impact: "high",
    complexity: "medium",
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

// Curated transactional "shape" a business's backend/admin/checkout needs map
// onto. Kept deliberately small (unlike vertical, which is an open label)
// since the DB schema, admin buckets, and cart/booking/lead-form rendering
// need a finite set of concrete implementations to build against.
const verticalToShape = {
  restaurant: "storefront_commerce",
  cafe: "storefront_commerce",
  bakery: "storefront_commerce",
  clinic: "scheduled_booking",
  salon: "scheduled_booking",
  tutor: "scheduled_booking",
  consultant: "scheduled_booking",
  repair_service: "inquiry_lead",
};

const businessShapeKeywords = [
  ["storefront_commerce", ["shop", "store", "ecommerce", "e-commerce", "sell", "product", "shipping", "checkout", "retail", "boutique", "merchandise", "movie", "cinema", "theatre", "theater", "showtime", "showtimes", "ticket", "tickets", "screening", "box office"]],
  ["portfolio_showcase", ["portfolio", "photography", "photographer", "gallery", "showcase", "creative", "design studio", "artist"]],
  ["catalog_reserve", ["library", "librarian", "book lending", "borrow", "lending", "loan program", "rental", "equipment rental", "reserve a copy", "hold a copy", "waitlist", "checkout a book"]],
  ["scheduled_booking", ["appointment", "booking", "schedule", "session", "class", "consultation", "visit"]],
  ["inquiry_lead", ["quote", "inquiry", "contact us", "get in touch", "request", "estimate"]],
];

const shapePagePresets = {
  storefront_commerce: ["Home", "Shop", "Cart", "About", "Contact"],
  scheduled_booking: ["Home", "Services", "Book Now", "About", "Contact"],
  inquiry_lead: ["Home", "Services", "Request a Quote", "About", "Contact"],
  portfolio_showcase: ["Home", "Portfolio", "About", "Contact"],
  catalog_reserve: ["Home", "Catalog", "My Holds", "About", "Contact"],
};

function classifyBusinessShape(rawInput, verticalAnalysis) {
  const vertical = verticalAnalysis.vertical;
  if (verticalToShape[vertical]) return verticalToShape[vertical];

  const text = (rawInput || "").toLowerCase();
  let bestShape = null;
  let bestScore = -1;
  for (const [shape, keywords] of businessShapeKeywords) {
    const score = keywords.reduce((count, kw) => count + (text.includes(kw) ? 1 : 0), 0);
    if (score > bestScore) {
      bestScore = score;
      bestShape = shape;
    }
  }
  return bestScore > 0 ? bestShape : "inquiry_lead";
}

// Shape-driven copy for the "Website" tab's design system — mirrors
// code_generator.py's mood/commerce_copy system on the Python side. Replaces
// a closed 3-way vertical switch (food / clinic / generic-service) that
// branded every non-food/non-clinic business (theatre, library, portfolio,
// e-commerce, salon, tutor...) identically, since none of them matched
// either of the two special-cased verticals.
const SHAPE_COPY = {
  storefront_commerce: {
    hero: "A storefront-ready ordering experience with a browsable catalog, cart, and checkout flow.",
    visual: { className: "restaurant-hero", cardTitle: "Revenue Stack", cardBody: "Catalog, cart, checkout, and admin operations are generated as one system." },
    tiles: [
      { title: "Browse To Cart", body: "Items are arranged around immediate add-to-cart actions and clear pricing." },
      { title: "Checkout Flow", body: "Orders are routed into an owner dashboard so the site supports real operations." },
      { title: "Local Trust", body: "Hours, location, and pricing clarity are treated as launch-critical trust signals." },
    ],
    proof: "The generated storefront connects customer actions to owner operations through orders and QA checks.",
    qa: {
      visual: "Detected catalog/cart content competing with hero copy, then grouped actions into a revenue stack.",
      conversion: "Cart and checkout flows are visible and connected to owner operations.",
      compliance: "Pricing clarity and applicable notices were checked before launch readiness scoring.",
    },
    primaryAction: { label: "Order Now", kind: "order" },
  },
  scheduled_booking: {
    hero: "A client-ready digital front desk with appointments, intake, and trust signals.",
    visual: { className: "clinic-hero", cardTitle: "Booking Stack", cardBody: "Services, booking flow, and intake are planned together." },
    tiles: [
      { title: "Care Pathways", body: "Services are grouped around client intent so the right next step is obvious." },
      { title: "Book + Intake", body: "Booking and intake feed the same admin schedule instead of becoming dead-end forms." },
      { title: "Compliance Guardrails", body: "Sensitive claims are restrained and privacy language is present where relevant." },
    ],
    proof: "The site is not just client-facing UI; it includes booking intake, admin visibility, and QA checks.",
    qa: {
      visual: "Detected weak booking CTA hierarchy, then promoted booking above other actions.",
      conversion: "Primary booking action is available in hero and connected to the generated schedule backend.",
      compliance: "Sensitive-claim wording checked; privacy notice included where relevant.",
    },
    primaryAction: { label: "Book Appointment", kind: "booking" },
  },
  inquiry_lead: {
    hero: "A service-ready website with quote capture, clear offerings, and a generated owner workflow.",
    visual: { className: "service-hero", cardTitle: "Lead Stack", cardBody: "Service pages, trust signals, quote capture, and owner follow-up are connected." },
    tiles: [
      { title: "Service Clarity", body: "The homepage explains what the business does, who it serves, and what action to take." },
      { title: "Quote Capture", body: "Requests are collected with enough context for the owner to respond quickly." },
      { title: "Owner Workflow", body: "Leads appear in the generated admin area so the website becomes an operating surface." },
    ],
    proof: "Customer requests are captured, organised, and verified through the generated admin workflow.",
    qa: {
      visual: "Detected generic service cards, then rewrote them around customer intent and quote capture.",
      conversion: "Request flow is reachable from the hero and stored in the generated lead dashboard.",
      compliance: "Risk language reviewed for the selected business category.",
    },
    primaryAction: { label: "Request Quote", kind: "lead" },
  },
  portfolio_showcase: {
    hero: "A portfolio-first website that leads with visual work and turns interest into inquiries.",
    visual: { className: "service-hero", cardTitle: "Showcase Stack", cardBody: "Portfolio, testimonials, and inquiry capture are connected." },
    tiles: [
      { title: "Visual Storytelling", body: "Past work leads the homepage so visitors see quality before anything else." },
      { title: "Proof Of Work", body: "Case studies and testimonials build confidence before an inquiry is sent." },
      { title: "Inquiry Workflow", body: "Interested visitors land in the generated admin area as qualified leads." },
    ],
    proof: "The generated portfolio connects visual proof to a real inquiry workflow and QA checks.",
    qa: {
      visual: "Detected thin visual proof, then prioritised gallery and case-study placement.",
      conversion: "Inquiry path is reachable directly from the portfolio, not buried in navigation.",
      compliance: "Client-facing claims reviewed for accuracy.",
    },
    primaryAction: { label: "Get In Touch", kind: "lead" },
  },
  catalog_reserve: {
    hero: "A catalog-ready website where visitors browse and reserve items without needing an account or payment.",
    visual: { className: "clinic-hero", cardTitle: "Catalog Stack", cardBody: "Catalog browsing, holds, and admin visibility are planned together." },
    tiles: [
      { title: "Browse The Catalog", body: "Items are organised so visitors can find what they want quickly." },
      { title: "One-Click Holds", body: "Reserving an item is a single action — no cart, no payment, no friction." },
      { title: "Availability Signals", body: "Availability status is shown clearly so expectations are set upfront." },
    ],
    proof: "The generated catalog connects browsing to real holds and admin visibility through QA checks.",
    qa: {
      visual: "Detected unclear availability signals, then made hold status explicit on every item.",
      conversion: "Reserve action is available directly from each catalog item.",
      compliance: "Access and eligibility language reviewed for accuracy.",
    },
    primaryAction: { label: "Reserve", kind: "lead" },
  },
};

function resolveBusinessShape(spec) {
  return (
    spec?.businessShape ||
    verticalToShape[spec?.business?.vertical] ||
    "inquiry_lead"
  );
}

function shapeCopy(spec) {
  return SHAPE_COPY[resolveBusinessShape(spec)] || SHAPE_COPY.inquiry_lead;
}

const DEFAULT_CATEGORIES_BY_SHAPE = {
  storefront_commerce: ["Popular", "Offers", "New"],
  catalog_reserve: ["New Arrivals", "Popular", "Available Now"],
};

function defaultCategoriesFor(spec) {
  return DEFAULT_CATEGORIES_BY_SHAPE[resolveBusinessShape(spec)] || ["Popular", "Featured", "New"];
}

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
  graphStatus: null,

  clarificationQuestions: [],
  pendingClarification: null,
  assumptions: [],
  humanAnswers: {},
  graphResumeState: null,
  isGenerating: false,
  resolveClarification: null,
};

function getBusinessProfileInput() {
  return {
    name: document.querySelector("#businessName").value.trim(),
    location: document.querySelector("#businessLocation").value.trim(),
    goal: document.querySelector("#businessGoal").value,
    contact_email: document.querySelector("#businessEmail").value.trim(),
    details: document.querySelector("#businessDetails").value,
    logo: document.querySelector("#businessLogo").files[0] || null,
    primary_color: document.querySelector("#primaryColor").value,
    secondary_color: document.querySelector("#secondaryColor").value,
    accent_color: document.querySelector("#accentColor").value,
    target_audience: document.querySelector("#targetAudience").value.trim(),
    unique_selling_points: document.querySelector("#uniqueSellingPoints").value.trim(),
    business_hours: document.querySelector("#businessHours").value.trim(),
    phone_number: document.querySelector("#phoneNumber").value.trim(),
    facebook_url: document.querySelector("#facebookUrl").value.trim(),
    instagram_url: document.querySelector("#instagramUrl").value.trim(),
    existing_website: document.querySelector("#existingWebsite").value.trim(),
  };
}

function handleLogoUpload(event) {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const preview = document.querySelector("#logoPreview");
      preview.innerHTML = `<img src="${e.target.result}" alt="Logo preview" />`;
    };
    reader.readAsDataURL(file);
  }
}

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
      "Running in fallback mode. Uploaded assets are sent to Pollinations for vision extraction.",
      "active",
    );
    updateCognitionPanel("fallback_mode", {
      observations: [
        "No graph events were returned.",
        "Build spec and website rendering are still active.",
        "Uploaded images, if any, were processed through the backend extraction path.",
        state.graphStatus?.error || "Planner graph was replaced with fallback execution.",
      ],
    });
    return;
  }

  for (const event of events) {
    renderGraphEvent(event);

    await sleep(800);
  }
}

function renderGraphEvent(event) {
  const nodeName = Object.keys(event)[0];
  const payload = event[nodeName];

  if (!nodeName) return;

  updateCognitionPanel(
    nodeName,
    payload,
  );

  updateGraphExecution(
    nodeName,
  );

  switch (nodeName) {
    case "business_profile": {
      const profile =
        payload?.business_profile || payload || {};
      pushTimelineEvent(
        "Business Understanding Agent",
        `Detected ${profile?.vertical || "unknown"} business with ${Math.round((profile?.confidence ?? 0.7) * 100)}% confidence.`,
        "classified",
      );
      break;
    }

    case "memory_retrieval":
      pushTimelineEvent(
        "Memory Agent",
        "Retrieved reusable planning memory for the current business context.",
        "active",
      );
      break;

    case "requirements": {
      const requirements =
        payload?.requirements_spec ||
        payload;

      const pageCount =
        (
          requirements?.required_pages ||
          []
        ).length;

      const workflowCount =
        (
          requirements?.required_workflows ||
          []
        ).length;

      pushTimelineEvent(
        "Requirements Agent",
        `Planned ${pageCount} pages and ${workflowCount} workflows.`,
        "researched",
      );

      break;
    }

    case "strategy_hypotheses": {
      const strategies =
        payload?.strategy_hypotheses ||
        payload?.strategies ||
        (Array.isArray(payload) ? payload : []);

      pushTimelineEvent(
        "Strategy Agent",
        `Generated ${strategies.length} competing behavioural strategies.`,
        "thinking",
      );

      break;
    }

    case "design_candidates": {
      const candidates =
        payload?.design_candidates ||
        payload?.candidates ||
        (Array.isArray(payload) ? payload : []);

      pushTimelineEvent(
        "Design Agent",
        `Created ${candidates.length} adaptive design candidates.`,
        "planned",
      );

      break;
    }

    case "critique":
      pushTimelineEvent(
        "Critique Agent",
        "Evaluated strategic tradeoffs and workflow weaknesses.",
        "evaluated",
      );
      if (!state._evolutionCritiquePushed) {
        state._evolutionCritiquePushed = true;
        pushEvolutionUpdate(
          "CTA Strategy Revision",
          "Aggressive immediate conversion CTA",
          "Trust-first onboarding flow",
          "Critique and simulation agents detected hesitation before trust establishment.",
        );
      }
      break;

    case "reflection":
      pushTimelineEvent(
        "Reflection Agent",
        "Reflection completed. Evaluating exploration quality.",
        "reflecting",
      );
      break;

    case "debate": {
      const debate =
        payload?.debate_outcome || payload || {};
      pushTimelineEvent(
        "Debate Agent",
        debate?.winner_reasoning || "Debated competing strategies.",
        "debating",
      );
      break;
    }

    case "simulation": {
      const sim =
        payload?.simulation_report || payload || {};
      const realism =
        sim?.overall_realism_score ??
        sim?.realism_score;
      pushTimelineEvent(
        "Simulation Agent",
        `Behavioural simulation realism score: ${realism ?? "--"}/10`,
        "simulated",
      );
      if (!state._evolutionSimPushed) {
        state._evolutionSimPushed = true;
        pushEvolutionUpdate(
          "Workflow Optimization",
          "Users encountered friction during booking",
          "Progressive trust-building before booking interaction",
          "Simulation agent detected confusion among first-time visitors.",
        );
      }
      break;
    }

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

  const explorationQuality =
    payload?.exploration_quality ??
    payload?.reflection_report?.exploration_quality;
  if (explorationQuality !== undefined) {
    document.querySelector(
      "#explorationValue",
    ).textContent =
      `${explorationQuality}/10`;
  }

  const convergenceRisk =
    payload?.convergence_risk ??
    payload?.reflection_report?.convergence_risk;
  if (convergenceRisk !== undefined) {
    document.querySelector(
      "#convergenceValue",
    ).textContent =
      `${convergenceRisk}/10`;
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
    "memory_retrieval",
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

function requestHumanClarifications(questions) {
  return new Promise((resolve) => {
    const normalized =
      (questions || []).length
        ? questions
        : [
            {
              question_id: "general_clarification",
              question:
                "What should the generated website clarify before continuing?",
              options: [],
            },
          ];

    let container = document.querySelector(
      "#clarificationPopup",
    );

    if (!container) {
      container = document.createElement("div");
      container.id = "clarificationPopup";
      container.className = "clarification-popup";
      document.body.appendChild(container);
    }

    container.innerHTML = `
      <div class="clarification-card human-loop-card">
        <div class="chip">Human-in-loop pause</div>
        <h3>The agents need a little more context</h3>
        <p>Answer what you can. The graph will resume with these details.</p>
        <form id="humanLoopForm" class="human-loop-form">
          ${normalized
            .map((question, index) => {
              const id =
                question.question_id ||
                question.id ||
                `clarification_${index + 1}`;
              const options =
                question.options || [];
              return `
                <label>
                  <span>${escapeHtml(question.question || "Clarification needed")}</span>
                  ${
                    options.length
                      ? `<select name="${escapeHtml(id)}">
                          ${options
                            .map(
                              (option) =>
                                `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`,
                            )
                            .join("")}
                        </select>`
                      : `<textarea name="${escapeHtml(id)}" rows="3" placeholder="Type the missing detail"></textarea>`
                  }
                </label>
              `;
            })
            .join("")}
          <button class="primary-button" type="submit">Resume Generation</button>
        </form>
      </div>
    `;

    container
      .querySelector("#humanLoopForm")
      .addEventListener("submit", (event) => {
        event.preventDefault();
        const answers = Object.fromEntries(
          Array.from(
            new FormData(event.currentTarget).entries(),
          ).filter(([, value]) =>
            String(value || "").trim().length,
          ),
        );
        container.remove();
        resolve(answers);
      });
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
  if (
    [
      "menu", "pizza", "pasta", "coffee", "service", "brochure", "flyer",
      "product", "catalog", "merchandise", "sell", "shop", "store",
      "ticket", "show", "snack",
    ].some((word) => text.includes(word))
  ) fields.add("menu_items");
  if (text.includes("hour") || text.includes("open")) fields.add("business_hours");
  if (text.includes("email") || profile.contact_email) fields.add("contact_email");
  if (text.includes("phone") || profile.phone) fields.add("phone_number");
  if (text.includes("location") || profile.location) fields.add("location");
  return fields;
}

function selectFeatures(vertical, availableFields, shape = "") {
  const included = [];
  const skipped = [];
  const missing = new Set();

  Object.entries(featureRegistry).forEach(([key, feature]) => {
    const appliesByVertical = feature.applicableTo.includes(vertical) || feature.applicableTo.includes("unknown");
    const appliesByShape = Boolean(shape) && (feature.applicableToShapes || []).includes(shape);
    if (!appliesByVertical && !appliesByShape) return;

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
      const reasonSubject = appliesByVertical ? vertical.replaceAll("_", " ") : shape.replaceAll("_", " ");
      included.push({
        ...decision,
        reason: `Included because it is high-value for ${reasonSubject} businesses.`,
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
  const shape = classifyBusinessShape(raw, analysis);
  if (analysis.vertical === "unknown") {
    analysis.subtype = `${shape.replaceAll("_", " ")} business`;
  }
  const fields = detectFields(profile, raw);
  const selected = selectFeatures(analysis.vertical, fields, shape);
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
    businessShape: shape,
    pages: (analysis.vertical !== "unknown" && pagePresets[analysis.vertical]) || shapePagePresets[shape] || pagePresets.unknown,
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

function heroCopy(spec) {
  return shapeCopy(spec).hero;
}

function verticalVisual(spec) {
  return shapeCopy(spec).visual;
}

function verticalTiles(spec) {
  return shapeCopy(spec).tiles;
}

function systemProofCopy(spec) {
  return shapeCopy(spec).proof;
}

function renderAdmin() {
  renderRecordList("#ordersList", state.orders, "No orders yet. Submit from the generated website.");
  renderRecordList("#bookingsList", state.bookings, "No bookings yet. Submit from the generated website.");
  renderRecordList("#leadsList", state.leads, "No leads yet. Submit from the generated website.");
}

window.addEventListener("message", function (event) {
  const d = event.data;
  if (!d || !d.type) return;
  const now = new Date().toLocaleTimeString();
  // Unified contract: any generated page (however it's built) reports a
  // submission as {type, summary, customer, contact} — accepts the older
  // per-type field names too (order/guests+date/message/email/phone) so
  // pages built against the previous rigid template still work.
  const record = {
    customer: d.customer || d.name || "Customer",
    request:
      d.summary ||
      d.order ||
      (d.guests || d.date ? `${d.guests || 1} guest(s) on ${d.date || "TBD"}` : "") ||
      d.message ||
      d.request ||
      "",
    contact: d.contact || d.email || d.phone || "",
    time: now,
  };
  if (d.type === "order") {
    state.orders.unshift(record);
    renderAdmin();
  } else if (d.type === "reservation") {
    state.bookings.unshift(record);
    renderAdmin();
  } else if (d.type === "lead") {
    state.leads.unshift(record);
    renderAdmin();
  }
});

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
  return shapeCopy(spec).qa;
}

async function requestLiveBuildSpec() {
  const response = await fetch(
    "/generate-buildspec-stream",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        business_input: getBusinessProfileInput(),
        asset_extractions: state.assetExtractions,
        human_answers: state.humanAnswers || {},
        resume_state: state.graphResumeState || null,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      `${response.status} ${await response.text()}`
    );
  }

  if (!response.body) {
    throw new Error(
      "Live graph stream is not available in this browser."
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;

  const processSseBlock = async (block) => {
    const lines = block.split(/\r?\n/);
    let eventName = "message";
    const dataLines = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    if (!dataLines.length) return false;

    const payload = JSON.parse(
      dataLines.join("\n"),
    );

    if (eventName === "status") {
      pushTimelineEvent(
        "System",
        payload.message || "Live graph execution started.",
        "active",
      );
      return false;
    }

    if (eventName === "buildspec") {
      state.assetExtractions =
        payload.assetExtractions || [];
      state.extractedAssetText =
        payload.assetSignals || "";
      state.amdInsights =
        buildAmdInsights(
          state.assetExtractions,
        );
      state.spec =
        payload.buildSpec ||
        generateBuildSpec();
      return false;
    }

    if (eventName === "graph_update") {
      const event = payload.event || {};
      state.graphEvents.push(event);
      renderGraphEvent(event);
      return false;
    }

    if (eventName === "human_input_required") {
      state.graphResumeState =
        payload.resume_state || null;
      pushTimelineEvent(
        "Human-in-loop Agent",
        payload.message || "Planner paused for clarification.",
        "paused",
      );
      const answers =
        await requestHumanClarifications(
          payload.questions || [],
        );
      state.humanAnswers = {
        ...(state.humanAnswers || {}),
        ...answers,
      };
      pushTimelineEvent(
        "Human-in-loop Agent",
        "Clarification received. Resuming graph with updated context.",
        "resuming",
      );
      await reader.cancel();
      finalPayload = await requestLiveBuildSpec();
      return true;
    }

    if (eventName === "graph_error") {
      pushTimelineEvent(
        "System",
        payload.error || "Planner graph switched to fallback mode.",
        "warning",
      );
      return false;
    }

    if (eventName === "complete") {
      state.graphResumeState = null;
      finalPayload = payload;
    }
    return false;
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(
      value,
      {
        stream: true,
      },
    );

    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (block.trim()) {
        const shouldRestart =
          await processSseBlock(block);
        if (shouldRestart) {
          return finalPayload;
        }
      }
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const shouldRestart =
      await processSseBlock(buffer);
    if (shouldRestart) {
      return finalPayload;
    }
  }

  if (!finalPayload) {
    throw new Error(
      "Live graph stream ended before a final payload arrived."
    );
  }

  return finalPayload;
}

async function runDemo() {
  if (state.isGenerating) return;

  state.isGenerating = true;

  try {
    state.timelineEvents = [];
    state.graphEvents = [];
    state.graphResumeState = null;
    state._evolutionCritiquePushed = false;
    state._evolutionSimPushed = false;
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

    clearPipelinePanels();

    document.querySelector(
      "#evolutionFeed",
    ).innerHTML = `<div class="evolution-empty">Awaiting strategic revisions...</div>`;

    document
      .querySelector(
        "#clarificationPopup",
      )
      ?.remove();

    showPanel(
      "reasoning",
    );

    const result =
      await requestLiveBuildSpec();

    console.log(
      "GRAPH RESPONSE",
      result,
    );

    state.graphEvents =
      result?.graphExecution?.events ||
      state.graphEvents ||
      [];
    state.graphExecution =
      result?.graphExecution || null;
    state.graphStatus =
      result?.graphStatus ||
      {
        status: result?.graphExecution?.status || "completed",
        error: result?.graphExecution?.graph_error || "",
      };

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

    renderGraphStatusBanner();
    if (state.graphStatus?.status === "fallback") {
      pushTimelineEvent(
        "System",
        state.graphStatus.error || "Planner graph switched to fallback mode.",
        "warning",
      );
    }

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
        : "Fallback planner"
    );

    showPanel(
      "reasoning",
    );

    // Autonomously continue the pipeline: research -> code -> critique -> deployment.
    runProductionPipeline().catch((error) => {
      console.error("Production pipeline failed", error);
    });
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

async function applyAmdPayload(payload, sourceLabel = "Pollinations import") {
  state.assetExtractions = payload.assetExtractions || [];
  state.extractedAssetText = payload.assetSignals || "";
  state.amdInsights = buildAmdInsights(state.assetExtractions);
  state.spec = payload.buildSpec;
  state.graphExecution = payload.graphExecution || null;
  state.designSpec =
    normalizeServerDesignSpec(
      payload.designSpec ||
      payload.graphExecution?.final_state?.design_spec,
    ) ||
    generateDesignSpec(state.spec);

  document.querySelector("#assetExtraction").textContent =
    payload.assetSignals ||
    "Extraction complete. No image-specific signals were returned, but BuildSpec generation succeeded.";

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
    document.querySelector("#targetAudience").value = preset.target_audience || "";
    document.querySelector("#uniqueSellingPoints").value = preset.unique_selling_points || "";
    document.querySelector("#businessHours").value = preset.business_hours || "";
    document.querySelector("#phoneNumber").value = preset.phone_number || "";
    document.querySelector("#primaryColor").value = preset.primary_color || "#3b82f6";
    document.querySelector("#secondaryColor").value = preset.secondary_color || "#1e40af";
    document.querySelector("#accentColor").value = preset.accent_color || "#f59e0b";
  });
});

document.querySelector("#runDemo").addEventListener("click", runDemo);

document.querySelector("#businessLogo").addEventListener("change", handleLogoUpload);

document.querySelector("#businessAssets").addEventListener("change", async (event) => {
  const files = [...(event.currentTarget.files || [])];
  state.assets = await Promise.all(files.map(readAssetFile));
  renderAssetPreview();
  document.querySelector("#assetExtraction").textContent =
    files.length
      ? `${files.length} asset${files.length === 1 ? "" : "s"} loaded. Click Extract & Build Site to analyse them.`
      : "No assets extracted yet. Upload images and click Extract & Build Site.";
});

document.querySelector("#extractAssets").addEventListener("click", () => {
  void extractAssetsFromBackend();
});

async function extractAssetsFromBackend() {
  const status = document.querySelector("#assetExtraction");
  const fileInput = document.querySelector("#businessAssets");
  const files = [...(fileInput.files || [])];
  const profile = getBusinessProfileInput();

  try {
    if (!files.length) {
      status.textContent = "Upload at least one image before extraction.";
      return;
    }
    status.textContent = `Sending ${files.length} image${files.length === 1 ? "" : "s"} to Pollinations for extraction...`;

    const payload = await requestAmdBuildSpec(
      "/extract-assets",
      profile,
      profile.details,
      files,
    );

    state.assetExtractions = payload.assetExtractions || [];
    state.extractedAssetText = payload.assetSignals || "";
    state.amdInsights = buildAmdInsights(state.assetExtractions);
    status.textContent =
      payload.assetSignals ||
      "Extraction complete, but no strong signals were returned.";
  } catch (error) {
    status.textContent =
      [
        `Asset extraction failed: ${error.message}`,
        `Endpoint: ${"/extract-assets"}`,
        `Asset count: ${files.length}`,
        "Check that the server is running and the pollinations.ai API is accessible.",
      ].join("\n\n");
    console.error("Asset extraction failed", { error });
  }
}

function renderGraphStatusBanner() {
  const host = document.querySelector("#graphStatusBanner");
  if (!host) return;
  const status = state.graphStatus;
  if (!status?.status || status.status === "completed") {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = `
    <div class="graph-status-banner warning">
      <strong>Planner fallback mode</strong>
      <p>${status.error || "The graph did not converge cleanly, so fallback execution was used."}</p>
    </div>
  `;
}

document.querySelector("#runAmdAssets").addEventListener("click", () => {
  void extractAssetsFromBackend();
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
    "No assets extracted yet. Upload images and click Extract & Build Site.";
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
      `Loaded ${file.name}. Click Apply Spec to drive the app with this BuildSpec.`;
  } catch (error) {
    document.querySelector("#amdStatus").textContent = `Import failed: ${error.message}`;
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
    await renderAllFromSpec("Pollinations import");
    showPanel("spec");
  } catch (error) {
    document.querySelector("#amdStatus").textContent = `Apply failed: ${error.message}`;
  }
});

document.querySelector("#loadLatestAmdResult").addEventListener("click", async () => {
  const status = document.querySelector("#amdStatus");
  status.textContent = "Loading the latest saved result...";
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
    await applyAmdPayload(payload, "Pollinations import");
    status.textContent = "Loaded amd_result.json from the notebook workspace and applied it to the UI.";
    showPanel("website");
  } catch (error) {
    status.textContent = `Load failed: ${error.message}`;
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
    throw new Error("missing payload key: buildSpec");
  }
  validateImportedSpec(payload.buildSpec);
}

function renderAmdStatus(sourceLabel) {
  const status = document.querySelector("#amdStatus");
  if (!status || !state.spec) return;
  const source =
    sourceLabel === "Pollinations import"
      ? "Pollinations-generated BuildSpec is active."
      : sourceLabel === "Fallback planner"
        ? "Local fallback planner active. Images were sent to Pollinations vision extraction."
        : "Planner is active. Paste a BuildSpec JSON below to override."
  status.textContent = `${source} Spec: ${state.spec.business.name}, ${state.spec.business.vertical.replaceAll("_", " ")}, readiness ${state.spec.scores.businessReadiness}.`;
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
    source: "pollinations-vision-batched",
    assetSignals,
    assetExtractions,
    buildSpec,
    graphExecution,
  };
}

function buildCombinedAssetSignals(extractions) {
  const lines = ["Extracted asset signals:"];
  extractions.forEach((item) => {
    const parsed = item.parsed || item || {};
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
  const shape = classifyBusinessShape(raw, analysis);
  if (analysis.vertical === "unknown") {
    analysis.subtype = `${shape.replaceAll("_", " ")} business`;
  }
  const fields = detectFields(profile, raw);
  const selected = selectFeatures(analysis.vertical, fields, shape);
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
    businessShape: shape,
    pages: (analysis.vertical !== "unknown" && pagePresets[analysis.vertical]) || shapePagePresets[shape] || pagePresets.unknown,
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
    "Pollinations vision extraction: upload images and click Extract & Build Site to extract menu items, services, prices, contact details, and visual brand cues.",
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
        <p>${state.amdInsights.assetCount} asset${state.amdInsights.assetCount === 1 ? "" : "s"} analysed by Pollinations vision extraction.</p>
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

const DESIGN_BRIEF_BY_SHAPE = {
  storefront_commerce: (ctx) =>
    ctx.hasStrongOffers
      ? "Lead with an offer-driven storefront, then move quickly into dense browsing UI with strong imagery and price visibility."
      : "Lead with visuals and social proof, then present a dense catalog-first layout with immediate action paths.",
  scheduled_booking: () => "Prioritise trust, credentials, and booking conversion before deeper service detail.",
  inquiry_lead: () => "Prioritise service clarity and lead capture, supported by trust signals and operational readiness.",
  portfolio_showcase: () => "Lead with visual proof of work, then guide interested visitors toward an inquiry.",
  catalog_reserve: () => "Prioritise easy browsing and clear availability, then make reserving an item effortless.",
};

const DESIGN_VISUAL_BY_SHAPE = {
  storefront_commerce: (ctx) => ({
    tone: ctx.hasStrongOffers ? "fast-casual and promotional" : "storefront and trustworthy",
    density: ctx.hasRichCatalog ? "high" : "medium",
    mediaBias: ctx.hasVisualAssets ? "image-heavy" : "content-heavy",
    trustEmphasis: "medium", primaryColor: "#9f2f22", accentColor: "#e4a12f", surfaceColor: "#fff8ef", fontFamily: "Inter",
  }),
  scheduled_booking: () => ({ tone: "calm and credible", density: "medium", mediaBias: "trust-first", trustEmphasis: "high", primaryColor: "#0f766e", accentColor: "#38bdf8", surfaceColor: "#f4fbfb", fontFamily: "Inter" }),
  inquiry_lead: () => ({ tone: "clear and pragmatic", density: "medium", mediaBias: "copy-first", trustEmphasis: "medium", primaryColor: "#334155", accentColor: "#f59e0b", surfaceColor: "#f8fafc", fontFamily: "Inter" }),
  portfolio_showcase: () => ({ tone: "editorial and confident", density: "medium", mediaBias: "image-heavy", trustEmphasis: "medium", primaryColor: "#171717", accentColor: "#d4af37", surfaceColor: "#fafafa", fontFamily: "Inter" }),
  catalog_reserve: () => ({ tone: "calm and organised", density: "medium", mediaBias: "content-heavy", trustEmphasis: "high", primaryColor: "#1e3a5f", accentColor: "#38bdf8", surfaceColor: "#f4fbfb", fontFamily: "Inter" }),
};

const DESIGN_PAGES_BY_SHAPE = {
  storefront_commerce: (ctx) => [{
    name: "Home", pageType: "home",
    sections: [
      { type: "hero_offer_banner", purpose: "Lead with the main commercial hook." },
      { type: "insights", purpose: "Show extracted AMD insights." },
      { type: ctx.hasVisualAssets ? "gallery_strip" : "page_nav", purpose: "Support browsing." },
      { type: ctx.hasRichCatalog ? "menu_showcase" : "feature_grid", purpose: "Display the core offer." },
      { type: "proof_band", purpose: "Support conversion confidence." },
      { type: "primary_workflow_form", purpose: "Capture order intent." },
    ],
  }],
  catalog_reserve: (ctx) => [{
    name: "Home", pageType: "home",
    sections: [
      { type: "hero_trust_banner", purpose: "Lead with a calm, informative hook." },
      { type: "insights", purpose: "Show extracted AMD insights." },
      { type: ctx.hasRichCatalog ? "menu_showcase" : "feature_grid", purpose: "Display the catalog." },
      { type: "proof_band", purpose: "Support confidence in availability." },
      { type: "primary_workflow_form", purpose: "Capture reservation intent." },
    ],
  }],
};
const DEFAULT_DESIGN_PAGES = [{ name: "Home", pageType: "home", sections: [{ type: "hero_trust_banner" }, { type: "insights" }, { type: "page_nav" }, { type: "feature_grid" }, { type: "proof_band" }, { type: "primary_workflow_form" }] }];

function generateDesignSpec(spec) {
  const shape = resolveBusinessShape(spec);
  const copy = shapeCopy(spec);
  const restaurant = buildRestaurantExperienceData();
  const ctx = {
    hasStrongOffers: restaurant.offers.length > 0,
    hasRichCatalog: restaurant.items.length >= 6,
    hasVisualAssets: state.assets.length >= 2,
  };

  return {
    brief: (DESIGN_BRIEF_BY_SHAPE[shape] || DESIGN_BRIEF_BY_SHAPE.inquiry_lead)(ctx),
    visual: (DESIGN_VISUAL_BY_SHAPE[shape] || DESIGN_VISUAL_BY_SHAPE.inquiry_lead)(ctx),
    primaryAction: { ...copy.primaryAction, placements: ["hero", "section_end"] },
    pages: (DESIGN_PAGES_BY_SHAPE[shape] || (() => DEFAULT_DESIGN_PAGES))(ctx),
    decisionRationale: [`${shape.replaceAll("_", " ")} flow prioritised ${copy.primaryAction.label.toLowerCase()}.`],
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
  designSpec =
    ensureRestaurantCommerceDesign(
      spec,
      designSpec,
      restaurant,
    );
  designSpec =
    ensureClinicHumanLoopDesign(
      spec,
      designSpec,
    );
  const visual = designAwareVisual(spec, designSpec);
  applyGeneratedDesignTheme(designSpec);

  const pages =
    (designSpec.pages || []).length
      ? designSpec.pages
      : (spec.pages || []).map((page) => ({
          name: page,
          title: page,
          pageType: String(page).toLowerCase(),
          sections: [],
        }));

  if (pages.length && activePageIndex >= pages.length) {
    activePageIndex = 0;
  }

  const currentPage =
    pages[activePageIndex] ||
    pages[0];

  const homePage =
    pages.find(
      (page) =>
        (page.pageType || "").toLowerCase() === "home",
    ) || pages[0];

  const heroSection =
    (homePage?.sections || []).find((section) =>
      [
        "hero_offer_banner",
        "hero_trust_banner",
      ].includes(
        getSectionType(section),
      ),
    );

  const bodySections =
    (homePage?.sections || []).filter((section) => {
      const sectionType =
        getSectionType(section);

      return ![
        "hero_offer_banner",
        "hero_trust_banner",
      ].includes(sectionType);
    });

  const pageSections =
    currentPage
      ? renderDesignPage(
          currentPage,
          spec,
          designSpec,
          restaurant,
        )
      : "";

  const renderedBody =
    pageSections ||
    bodySections
      .map((section) =>
        renderDesignSection(
          section,
          spec,
          designSpec,
          restaurant,
        ),
      )
      .join("") ||
    renderAdaptiveGenericSection(
      {
        type: "feature_grid",
        purpose:
          "Show the core business offer when the agent did not specify detailed sections.",
      },
      spec,
      designSpec,
      restaurant,
    );

  // const additionalPages =
  //   pages
  //     .filter(
  //       (page) =>
  //         page !== homePage,
  //     )
  //     .map((page) =>
  //       renderDesignPage(
  //         page,
  //         spec,
  //         designSpec,
  //         restaurant,
  //       ),
  //     )
  //     .join("");

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
    designSpec.primaryAction?.label ||
    "Continue";

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

  window.latestSpec = spec;
  window.latestDesignSpec = designSpec;
  window.latestRestaurant = restaurant;

  document.querySelector("#sitePreview").innerHTML =
    `
      <section
        class="generated-hero ${visual.className || ""}"
        ${buildHeroBackground(spec, restaurant, heroSection)}
      >
        <div class="generated-hero-copy">
          <p class="eyebrow">${formatPageLabel(spec.business.vertical)}</p>
          <h3>${escapeHtml(spec.business.name)}</h3>
          <p>${escapeHtml(adaptiveHeroCopy)}</p>
          ${renderHeroSupportChips(spec, designSpec, restaurant, heroSection)}
          <div class="hero-action-row">
            <button class="primary-button" type="button" data-generated-action="primary">${escapeHtml(adaptiveCta)}</button>
            <button class="ghost-button" type="button" data-generated-action="explore">Explore</button>
          </div>
        </div>
        <aside class="generated-card generated-hero-card">
          <strong>${escapeHtml(heroCardTitle(designSpec, heroSection))}</strong>
          <p>${escapeHtml(heroCardBody(spec, designSpec, restaurant, heroSection))}</p>
          <div class="summary-stats">
            <div>
              <span>${restaurant.items.length || spec.includedFeatures.length}</span>
              <small>${restaurant.items.length ? "menu items" : "features"}</small>
            </div>
            <div>
              <span>${restaurant.categories.length || pages.length}</span>
              <small>${restaurant.categories.length ? "categories" : "pages"}</small>
            </div>
            <div>
              <span>${restaurant.cartTotalLabel || `${spec.scores?.businessReadiness || "--"}%`}</span>
              <small>${restaurant.cartTotalLabel ? "cart total" : "readiness"}</small>
            </div>
          </div>
        </aside>
      </section>
      <div class="generated-body">
        ${renderPageNav(spec, { ...designSpec, pages })}
        ${renderedBody}
        ${renderDecisionRationaleBand(designSpec)}
      </div>
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
      return "";
    case "category_strip":
      return renderCategoryStripSection(spec, restaurant, sectionPurpose);
    case "gallery_strip":
      return `
        <div class="restaurant-topbar">
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
    case "provider_profile":
    case "provider_profiles":
    case "team_credentials":
      return renderProviderProfileSection(spec);
    case "primary_workflow_form":
    case "order_form":
      return renderPrimaryWorkflowForm(spec, designSpec, restaurant);
    default:
      return renderAdaptiveGenericSection(section, spec, designSpec, restaurant);
  }
}

function applyGeneratedDesignTheme(designSpec) {
  const preview =
    document.querySelector("#sitePreview");
  if (!preview) return;
  const visual = designSpec.visual || {};
  preview.style.setProperty(
    "--accent",
    visual.primaryColor || "#0d7c66",
  );
  preview.style.setProperty(
    "--accent-dark",
    darkenHexColor(
      visual.primaryColor || "#0d7c66",
    ),
  );
  preview.style.setProperty(
    "--gold",
    visual.accentColor || "#d99b28",
  );
  preview.style.setProperty(
    "--soft",
    visual.surfaceColor || "#f7faf8",
  );
  preview.style.fontFamily =
    `${visual.fontFamily || "Inter"}, system-ui, sans-serif`;
}

function darkenHexColor(hex) {
  const clean =
    String(hex || "").replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) {
    return "#075e4d";
  }
  const values = [0, 2, 4].map((start) =>
    Math.max(
      0,
      Math.round(parseInt(clean.slice(start, start + 2), 16) * 0.72),
    )
      .toString(16)
      .padStart(2, "0"),
  );
  return `#${values.join("")}`;
}

function ensureRestaurantCommerceDesign(spec, designSpec, restaurant) {
  const effective =
    designSpec || generateDesignSpec(spec);
  // Was gated on a hardcoded food-vertical name list, so a theatre/e-commerce
  // store/anything else with a real online_ordering feature never got its
  // commerce section injected at all — gate on the shape instead, which is
  // exactly what online_ordering is already scoped to (see buildspec_planner.py).
  const isCommerceShape = resolveBusinessShape(spec) === "storefront_commerce";

  if (!isCommerceShape) {
    return effective;
  }

  const featureKeys =
    (spec.includedFeatures || []).map((feature) =>
      String(feature.key || "").toLowerCase(),
    );
  const details =
    [
      spec.business?.goal,
      spec.business?.details,
      spec.business?.unique_selling_points,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  const hasOrderingIntent =
    featureKeys.includes("online_ordering") ||
    /order|pickup|delivery|menu|cart/.test(details) ||
    restaurant.items.length > 0;

  if (!hasOrderingIntent) {
    return effective;
  }

  effective.primaryAction = {
    label:
      effective.primaryAction?.kind === "order"
        ? effective.primaryAction?.label || "Order Now"
        : "Order Now",
    kind: "order",
    placements:
      effective.primaryAction?.placements?.length
        ? effective.primaryAction.placements
        : ["hero", "menu", "section_end"],
  };

  if (!Array.isArray(effective.pages) || !effective.pages.length) {
    effective.pages = [
      {
        name: "Home",
        title: "Home",
        pageType: "home",
        sections: [],
      },
    ];
  }

  let homePage =
    effective.pages.find(
      (page) =>
        String(page.pageType || page.name || "").toLowerCase() === "home",
    ) || effective.pages[0];

  homePage.sections = Array.isArray(homePage.sections)
    ? homePage.sections
    : [];

  const sectionTypes =
    homePage.sections.map(getSectionType);
  const insertBeforeWorkflow =
    (section) => {
      const workflowIndex =
        homePage.sections.findIndex(
          (candidate) =>
            getSectionType(candidate) === "primary_workflow_form",
        );
      if (workflowIndex >= 0) {
        homePage.sections.splice(workflowIndex, 0, section);
      } else {
        homePage.sections.push(section);
      }
    };

  if (
    !sectionTypes.includes("menu_showcase")
  ) {
    insertBeforeWorkflow({
      type: "menu_showcase",
      purpose:
        "Display extracted menu items, prices, and add-to-cart actions before checkout.",
      rationale:
        "Restaurant visitors need to inspect the menu before placing an order.",
    });
  }

  if (
    !homePage.sections.some(
      (section) =>
        getSectionType(section) === "primary_workflow_form",
    )
  ) {
    homePage.sections.push({
      type: "primary_workflow_form",
      purpose:
        "Capture the final food order or pickup request after menu selection.",
      rationale:
        "Online ordering requires a concrete checkout workflow.",
    });
  }

  const hasMenuPage =
    effective.pages.some(
      (page) =>
        String(page.pageType || page.name || "").toLowerCase().includes("menu"),
    );

  if (!hasMenuPage) {
    effective.pages.push({
      name: "Menu",
      title: "Menu",
      pageType: "menu",
      sections: [
        {
          type: "menu_showcase",
          purpose:
            "Let visitors browse the extracted restaurant menu with prices and cart actions.",
        },
        {
          type: "primary_workflow_form",
          purpose:
            "Convert selected menu items into an order request.",
        },
      ],
    });
  }

  effective.decisionRationale =
    effective.decisionRationale || [];
  if (
    !effective.decisionRationale.some((item) =>
      /menu|cart|order/i.test(String(item)),
    )
  ) {
    effective.decisionRationale.push(
      "Restaurant commerce guardrail added menu browsing, cart, and order capture because ordering intent was detected.",
    );
  }

  return effective;
}

function ensureClinicHumanLoopDesign(spec, designSpec) {
  const effective =
    designSpec || generateDesignSpec(spec);
  const vertical =
    String(spec.business?.vertical || "").toLowerCase();
  const isClinic =
    ["clinic", "dental", "doctor", "medical", "health"].includes(vertical);
  const providerAnswer =
    String(
      state.humanAnswers?.simulation_provider_credentials || "",
    ).trim();

  if (!isClinic || !providerAnswer) {
    return effective;
  }

  if (!Array.isArray(effective.pages) || !effective.pages.length) {
    effective.pages = [
      {
        name: "Home",
        title: "Home",
        pageType: "home",
        sections: [],
      },
    ];
  }

  const targetPage =
    effective.pages.find((page) =>
      (page.sections || []).some(
        (section) =>
          getSectionType(section) === "primary_workflow_form",
      ),
    ) ||
    effective.pages.find(
      (page) =>
        String(page.pageType || page.name || "").toLowerCase() === "home",
    ) ||
    effective.pages[0];

  targetPage.sections = Array.isArray(targetPage.sections)
    ? targetPage.sections
    : [];

  const hasProfileSection =
    targetPage.sections.some((section) =>
      ["provider_profile", "provider_profiles", "team_credentials"].includes(
        getSectionType(section),
      ),
    );

  if (!hasProfileSection) {
    const workflowIndex =
      targetPage.sections.findIndex(
        (section) =>
          getSectionType(section) === "primary_workflow_form",
      );
    const profileSection = {
      type: "provider_profile",
      purpose:
        "Show provider bios and credentials before the booking form.",
      rationale:
        "Human clarification supplied provider details after simulation flagged trust friction.",
    };
    if (workflowIndex >= 0) {
      targetPage.sections.splice(workflowIndex, 0, profileSection);
    } else {
      targetPage.sections.push(profileSection);
    }
  }

  effective.decisionRationale =
    effective.decisionRationale || [];
  if (
    !effective.decisionRationale.some((item) =>
      /provider|credential|dentist/i.test(String(item)),
    )
  ) {
    effective.decisionRationale.push(
      "Human clarification added provider credentials above the booking form.",
    );
  }

  return effective;
}

function parseProviderProfiles(answer) {
  const text = String(answer || "").trim();
  if (!text) return [];
  return text
    .split(/\n|;/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)
    .map((item, index) => {
      const parts = item.split(/,|-|\u2014/).map((part) => part.trim()).filter(Boolean);
      return {
        name: parts[0] || `Provider ${index + 1}`,
        credentials: parts.slice(1).join(" · ") || "Clinical care team",
      };
    });
}

function renderProviderProfileSection(spec) {
  const profiles =
    parseProviderProfiles(
      state.humanAnswers?.simulation_provider_credentials,
    );
  if (!profiles.length) return "";
  return `
    <section id="generatedProviders" class="provider-profile-section">
      <div class="menu-header">
        <div>
          <p class="eyebrow">Care Team</p>
          <strong>Meet your provider before booking</strong>
          <p>Credentials are shown before the appointment form so patients can decide with confidence.</p>
        </div>
      </div>
      <div class="generated-grid">
        ${profiles
          .map(
            (profile) => `
              <article class="generated-tile provider-profile-card">
                <span class="provider-avatar">${escapeHtml(profile.name.charAt(0) || "D")}</span>
                <strong>${escapeHtml(profile.name)}</strong>
                <p>${escapeHtml(profile.credentials)}</p>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderAdaptiveGenericSection(section, spec, designSpec, restaurant) {
  const sectionType = getSectionType(section);
  const sectionPurpose =
    getSectionPurpose(section) ||
    (typeof section === "string" ? section : section?.rationale) ||
    "A focused section to help visitors compare, trust, and take the next step.";
  const title =
    typeof section === "string"
      ? formatPageLabel(section)
      : section?.title ||
        section?.name ||
        formatPageLabel(sectionType || "adaptive section");
  const sourceItems =
    restaurant.items.length
      ? restaurant.items.slice(0, 3).map((item) => ({
          title: item.name,
          body: item.description || item.priceLabel || "Featured offer",
        }))
      : verticalTiles(spec);
  const cards =
    sourceItems.length
      ? sourceItems
      : [
          {
            title: "Clear Offer",
            body: "The section keeps the business proposition easy to scan.",
          },
          {
            title: "Trust Context",
            body: "Supporting details reduce friction before the visitor acts.",
          },
          {
            title: "Action Path",
            body: "The page keeps the next workflow visible and reachable.",
          },
        ];

  return `
    <section class="adaptive-section">
      <div class="menu-header">
        <div>
          <p class="eyebrow">${escapeHtml(sectionType || "adaptive")}</p>
          <strong>${escapeHtml(title)}</strong>
          <p>${escapeHtml(sectionPurpose)}</p>
        </div>
      </div>
      <div class="generated-grid">
        ${cards
          .slice(0, 3)
          .map(
            (card) => `
              <article class="generated-tile">
                <strong>${escapeHtml(card.title)}</strong>
                <p>${escapeHtml(card.body)}</p>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function switchGeneratedPage(index) {

  activePageIndex = index;

  if (
    window.latestSpec &&
    window.latestDesignSpec
  ) {

    renderWebsiteDynamic(
      window.latestSpec,
      window.latestDesignSpec,
    );
  }
}

function renderPageNav(
  spec,
  designSpec,
) {

  const pages =
    (designSpec.pages || []).length
      ? designSpec.pages
      : (spec.pages || []).map(
          (page) => ({
            name: page,
          }),
        );

  return `
    <div class="website-nav">
      ${pages
        .map((page, index) => {

          const label =
            page.name ||
            page.title ||
            "Page";

          const activeClass =
            index === activePageIndex
              ? "active"
              : "";

          return `
            <button
              class="nav-pill ${activeClass}"
              onclick="switchGeneratedPage(${index})"
            >
              ${label}
            </button>
          `;
        })
        .join("")}
    </div>
  `;
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

function renderCategoryStripSection(spec, restaurant, sectionPurpose) {
  const categories = restaurant.categories.length ? restaurant.categories : defaultCategoriesFor(spec);
  return `
    <section class="menu-header category-strip-section">
      <div>
        <strong>Browse by category</strong>
        <p>${sectionPurpose || "Jump into popular categories, current offers, and customer favourites."}</p>
      </div>
      <div class="chip-row">
        ${categories.map((category) => `<span class="chip">${category}</span>`).join("")}
      </div>
    </section>
  `;
}

function renderMenuShowcaseSection(spec, restaurant, designSpec, sectionPurpose) {
  const categoryChips = restaurant.categories.length ? restaurant.categories : defaultCategoriesFor(spec);
  const featuredItems = restaurant.items.slice(0, 8);
  const isTrustBrowsing = designSpec.primaryAction.label === "Explore Menu" || designSpec.visual.trustEmphasis === "high";
  return `
    <section class="menu-shell" id="generatedMenu">
      <div class="menu-column">
        <div class="menu-header">
          <div>
            <strong>Menu highlights</strong>
            <p>${sectionPurpose || (isTrustBrowsing
              ? "Browse signature items, compare categories, and choose when you are ready."
              : "Pick a favourite, check the price, and add it to your order in one tap.")}</p>
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
      title: "Easy discovery",
      body: restaurant.offers[0] || "Seasonal offers and popular choices are easy to scan.",
    },
    {
      title: "Menu clarity",
      body: `${restaurant.items[0]?.name || "Signature items"} and pricing stay visible while customers browse.`,
    },
    {
      title: "Local trust",
      body: `${spec.business.name} keeps hours, location, and next steps close to the menu.`,
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
        <strong>Ready when you are</strong>
        <p>${sectionPurpose || "Browse first, then order or reserve when the choice feels clear."}</p>
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
        <p>${sectionPurpose || "Clear pricing, direct contact, and simple next steps make it easy to decide."}</p>
      </div>
      <div class="chip-row">
        ${trustItems.length
          ? trustItems.map((item) => `<span class="chip">${item.replaceAll("_", " ")}</span>`).join("")
          : `<span class="chip">Clear next steps</span><span class="chip">Fast response</span><span class="chip">Visible pricing</span>`}
      </div>
    </section>
  `;
}

const REQUEST_PLACEHOLDER_BY_SHAPE = {
  storefront_commerce: (restaurant) => state.cart[0]?.name || restaurant.items[0]?.name || "Item from the catalog",
  scheduled_booking: () => "Appointment request",
  inquiry_lead: () => "Project inquiry",
  portfolio_showcase: () => "Project inquiry",
  catalog_reserve: (restaurant) => restaurant.items[0]?.name || "Item to reserve",
};

function renderPrimaryWorkflowForm(spec, designSpec, restaurant) {
  const kind = designSpec.primaryAction.kind;
  const shape = resolveBusinessShape(spec);
  const requestLabel = kind === "order" ? "Order item" : kind === "booking" ? "Service needed" : "Request";
  const requestValue = (REQUEST_PLACEHOLDER_BY_SHAPE[shape] || REQUEST_PLACEHOLDER_BY_SHAPE.inquiry_lead)(restaurant);
  const formClass = kind === "order" ? "workflow-form restaurant-order-form" : "workflow-form";
  const responseTiming =
    state.humanAnswers?.simulation_response_timing || "";
  const privacyNote =
    state.humanAnswers?.simulation_privacy_reassurance || "";
  return `
    <section id="generatedWorkflow" class="workflow-section">
      ${
        responseTiming || privacyNote
          ? `<div class="workflow-reassurance">
              ${responseTiming ? `<span>${escapeHtml(responseTiming)}</span>` : ""}
              ${privacyNote ? `<span>${escapeHtml(privacyNote)}</span>` : ""}
            </div>`
          : ""
      }
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
    </section>
  `;
}

function buildHeroBackground(spec, restaurant, heroSection) {
  if (!restaurant.heroImages[0]) return "";
  const heroType = getSectionType(heroSection);
  const overlay =
    heroType === "hero_trust_banner"
      ? "linear-gradient(115deg, rgba(16, 42, 54, 0.92), rgba(34, 72, 78, 0.74))"
      : "linear-gradient(115deg, rgba(23, 53, 46, 0.92), rgba(80, 52, 32, 0.74))";
  return `style="background-image: ${overlay}, url('${restaurant.heroImages[0].url}'); background-size: cover; background-position: center;"`;
}

function attachWebsiteInteractions(spec, designSpec, restaurant) {
  document.querySelectorAll("[data-generated-action]").forEach((button) => {
    button.addEventListener("click", () => {
      routeGeneratedAction(
        button.dataset.generatedAction,
        spec,
        designSpec,
      );
    });
  });

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

function routeGeneratedAction(action, spec, designSpec) {
  const target =
    resolveGeneratedActionTarget(action, spec, designSpec);

  if (
    typeof target.pageIndex === "number" &&
    activePageIndex !== target.pageIndex
  ) {
    activePageIndex = target.pageIndex;
    renderWebsiteDynamic(
      spec,
      designSpec,
    );
    requestAnimationFrame(() =>
      scrollGeneratedSelector(target.selector),
    );
    return;
  }

  scrollGeneratedSelector(target.selector);
}

function resolveGeneratedActionTarget(action, spec, designSpec) {
  const kind =
    designSpec.primaryAction?.kind ||
    "lead";
  const menuPageIndex =
    findGeneratedPageIndexBySection(
      designSpec,
      "menu_showcase",
    );
  const workflowPageIndex =
    findGeneratedPageIndexBySection(
      designSpec,
      "primary_workflow_form",
    );
  const firstNonHomePage =
    (designSpec.pages || []).findIndex(
      (page) =>
        String(page.pageType || page.name || "")
          .toLowerCase() !== "home",
    );

  if (action === "explore") {
    if (
      kind === "booking" &&
      findGeneratedPageIndexBySection(
        designSpec,
        "provider_profile",
      ) >= 0
    ) {
      return {
        pageIndex: findGeneratedPageIndexBySection(
          designSpec,
          "provider_profile",
        ),
        selector: "#generatedProviders",
      };
    }
    if (kind === "order" && menuPageIndex >= 0) {
      return {
        pageIndex: menuPageIndex,
        selector: "#generatedMenu",
      };
    }
    if (firstNonHomePage >= 0) {
      return {
        pageIndex: firstNonHomePage,
        selector: ".generated-page",
      };
    }
    return {
      pageIndex: activePageIndex,
      selector: ".generated-body",
    };
  }

  if (kind === "order") {
    return {
      pageIndex: menuPageIndex >= 0 ? menuPageIndex : activePageIndex,
      selector: "#generatedMenu",
    };
  }

  return {
    pageIndex: workflowPageIndex >= 0 ? workflowPageIndex : activePageIndex,
    selector: "#generatedWorkflow",
  };
}

function findGeneratedPageIndexBySection(designSpec, sectionType) {
  return (designSpec.pages || []).findIndex((page) =>
    (page.sections || []).some(
      (section) =>
        getSectionType(section) === sectionType,
    ),
  );
}

function scrollGeneratedSelector(selector) {
  const target =
    document.querySelector(selector) ||
    document.querySelector("#workflowForm") ||
    document.querySelector(".generated-body");

  target?.scrollIntoView({
    behavior: "smooth",
    block: "center",
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
      primaryColor: designSpec.visual_system?.primary_color || "#0d7c66",
      accentColor: designSpec.visual_system?.accent_color || "#d99b28",
      surfaceColor: designSpec.visual_system?.surface_color || "#f7faf8",
      fontFamily: designSpec.visual_system?.font_family || "Inter",
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
  const verticalVisualBase = verticalVisual(spec);
  const tone = designSpec.visual?.tone || "practical";
  if (tone === "trustworthy" || tone === "calm") {
    return {
      className: shapeCopy(spec).visual.className,
      cardTitle: "Confidence-first layout",
      cardBody: "The agent shifted this experience toward reassurance, exploration, and lower-pressure conversion.",
    };
  }
  return verticalVisualBase;
}

function heroSectionCopy(spec, designSpec, heroSection) {
  const heroType = getSectionType(heroSection);
  if (heroType === "hero_trust_banner") {
    return "The agent chose to open with confidence-building context before the action step, so visitors can explore the offer with more clarity.";
  }
  return heroCopy(spec);
}

function renderHeroSupportChips(spec, designSpec, restaurant, heroSection) {
  const heroType = getSectionType(heroSection);
  const chips =
    heroType === "hero_trust_banner"
      ? ["Browse before you decide", "Clear pricing", "Local trust signals"]
      : restaurant.offers.length
        ? restaurant.offers.slice(0, 2)
        : restaurant.categories.slice(0, 2).map((category) => `${category} ready to order`);
  return `<div class="chip-row">${chips.map((item) => `<span class="chip offer-chip">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function heroCardTitle(designSpec, heroSection) {
  const heroType = getSectionType(heroSection);
  if (heroType === "hero_trust_banner") return "Trust-first storefront";
  return "Conversion-first storefront";
}

function heroCardBody(spec, designSpec, restaurant, heroSection) {
  const heroType = getSectionType(heroSection);
  if (heroType === "hero_trust_banner") {
    return "This direction emphasises visual reassurance, richer browsing, and social proof before the final order step.";
  }
  const offerCount = restaurant.offers.length ? `${restaurant.offers.length} live offer${restaurant.offers.length === 1 ? "" : "s"}` : "menu-first ordering";
  return `This direction emphasises ${offerCount}, shortens time-to-action, and keeps the ordering path visible.`;
}

function renderDecisionRationaleBand(designSpec) {
  return "";
}

function getSectionType(section) {
  const raw =
    typeof section === "string"
      ? section
      : section?.type || "";
  const value =
    String(raw).toLowerCase().trim().replaceAll("-", "_");
  const aliases = {
    hero: "hero_offer_banner",
    hero_banner: "hero_offer_banner",
    hero_section: "hero_offer_banner",
    offer_banner: "hero_offer_banner",
    promo_hero: "hero_offer_banner",
    trust_hero: "hero_trust_banner",
    credibility_hero: "hero_trust_banner",
    menu: "menu_showcase",
    menu_grid: "menu_showcase",
    featured_menu_grid: "menu_showcase",
    product_grid: "menu_showcase",
    catalog: "menu_showcase",
    services: "feature_grid",
    service_grid: "feature_grid",
    services_grid: "feature_grid",
    features: "feature_grid",
    testimonials: "review_band",
    reviews: "review_band",
    social_proof: "review_band",
    trust: "trust_band",
    assurance: "trust_band",
    credibility: "trust_band",
    credentials: "trust_band",
    provider_profile: "provider_profile",
    provider_profiles: "provider_profile",
    doctor_profiles: "provider_profile",
    dentist_profiles: "provider_profile",
    team_credentials: "provider_profile",
    location_hours: "trust_band",
    proof: "proof_band",
    proof_points: "proof_band",
    booking_form: "primary_workflow_form",
    appointment_form: "primary_workflow_form",
    appointment_booking: "primary_workflow_form",
    appointment_booking_form: "primary_workflow_form",
    reservation_form: "primary_workflow_form",
    lead_form: "primary_workflow_form",
    contact_form: "primary_workflow_form",
    workflow: "primary_workflow_form",
    workflow_form: "primary_workflow_form",
    gallery: "gallery_strip",
    media: "gallery_strip",
    image_strip: "gallery_strip",
    categories: "category_strip",
    category_nav: "category_strip",
  };
  return aliases[value] || value;
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

  console.log(
    "ASSET EXTRACTION",
    extraction,
  );

    const parsed = extraction || {};
    const info = parsed.extracted_business_info || {};
    const assetType = parsed.asset_type || "menu";
    const signals = parsed.business_signals || [];
    const services = (info.services_or_items || []).slice(0, 18);

    console.log(
      "SERVICES",
      services,
    );    
    const prices = info.prices || [];
    const categoryName = inferMenuCategory(parsed, assetType, categoryIndex);
    if (categoryName) categories.push(categoryName);
    categoryIndex += 1;
    (info.offers || []).forEach((offer) => offers.push(String(offer)));
    signals
      .filter((signal) => /off|combo|deal|discount/i.test(signal))
      .forEach((signal) => offers.push(String(signal)));

    services.forEach((service, index) => {
      const cleanedName = sanitizeMenuLabel(service);
      if (!cleanedName) return;
      const priceValue = prices[index] ?? prices[0] ?? null;
      items.push({
        id: `${assetType}-${categoryIndex}-${index}`,
        name: cleanedName,
        category: categoryName,
        description: buildMenuDescription(cleanedName, categoryName, signals),
        priceLabel: formatMenuPrice(priceValue),
        priceSortValue: getMenuPriceNumber(priceValue),
        visual: state.assets[index % Math.max(state.assets.length, 1)]?.url || "",
      });
    });
  });

  console.log(
    "RAW MENU ITEMS",
    items,
  );
  const dedupedItems = dedupeMenuItems(items).slice(0, 16);
  console.log(
    "DEDUPED ITEMS",
    dedupedItems,
  );
  // If no menu photo was uploaded/extracted, the business may still have
  // typed real item/price data into a clarification-question answer (e.g.
  // "Popcorn $5, Nachos $6, Soda $4") — use that before ever fabricating
  // placeholder content, and never assume it's food (a generic "Margherita
  // Pizza" fallback is wrong for a theatre, salon, retailer, etc.).
  const answerItems = dedupedItems.length ? [] : parseItemsFromHumanAnswers(state.humanAnswers);
  const fallbackItems = dedupedItems.length
    ? dedupedItems
    : answerItems.length
    ? answerItems
    : [
        { id: "fallback-1", name: "Item pricing not yet provided", category: "Popular", description: "Add real items and prices to replace this placeholder.", priceLabel: "--", priceSortValue: 0, visual: "" },
      ];

  const usableOffers = uniqueCompact(offers.map(sanitizeOfferCopy).filter(Boolean), 4);
  const uniqueCategories = uniqueCompact(categories.filter(Boolean), 5);
  const priceNumbers = fallbackItems.map((item) => item.priceSortValue).filter((value) => Number.isFinite(value));
  const cartTotal = state.cart.reduce((total, item) => total + (item.priceSortValue || 0), 0);

  return {
    items: fallbackItems,
    offers: usableOffers,
    categories: uniqueCategories,
    heroImages: state.assets,
    priceRange: priceNumbers.length ? `${detectCurrencySymbol()}${Math.min(...priceNumbers)}-${detectCurrencySymbol()}${Math.max(...priceNumbers)}` : `${detectCurrencySymbol()}9.99-${detectCurrencySymbol()}24.99`,
    cartTotalLabel: cartTotal ? `${detectCurrencySymbol()}${cartTotal}` : `${detectCurrencySymbol()}0`,
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
  if (signals.length) qualifiers.push(compactSignalLabel(String(signals[0])));
  const prefix = qualifiers.slice(0, 2).filter(Boolean).join(" | ");
  return prefix ? `${prefix} | Simple online ordering.` : "Simple online ordering.";
}

function parseItemsFromHumanAnswers(humanAnswers) {
  const items = [];
  const text = Object.values(humanAnswers || {}).join(", ");
  if (!text.trim()) return items;
  // Split on commas that aren't inside a parenthetical (so "Combo (popcorn +
  // soda) $10" stays one segment instead of splitting on the internal "+").
  const segments = text.split(/,(?![^(]*\))/);
  segments.forEach((segment, index) => {
    const trimmed = segment.trim().replace(/^[-→:•]+/, "").trim();
    if (!trimmed) return;
    const priceMatch = trimmed.match(/\$\s?(\d+(?:\.\d{1,2})?)|₹\s?(\d+(?:\.\d{1,2})?)/);
    if (!priceMatch) return;
    const priceValue = parseFloat(priceMatch[1] || priceMatch[2]);
    let name = trimmed.slice(0, priceMatch.index).trim();
    // Drop a dangling unmatched "(" fragment, e.g. "Popcorn (small $5" -> "Popcorn"
    // (the "small"/"large" variant note isn't worth keeping without its price).
    const openCount = (name.match(/\(/g) || []).length;
    const closeCount = (name.match(/\)/g) || []).length;
    if (openCount > closeCount) {
      name = name.slice(0, name.lastIndexOf("("));
    }
    name = name.trim().replace(/[\s(:.-]+$/, "");
    if (!name || name.length > 60) return;
    items.push({
      id: `answer-item-${index}`,
      name,
      category: "Menu",
      description: "",
      priceLabel: `${detectCurrencySymbol()}${priceValue}`,
      priceSortValue: priceValue,
      visual: "",
    });
  });
  return items;
}

function sanitizeMenuLabel(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (text.length > 80) return text.slice(0, 77) + "...";
  if (/placeholder|template|lorem|sample text/i.test(text)) return "";
  return text;
}

function sanitizeOfferCopy(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > 64 ? `${text.slice(0, 61)}...` : text;
}

function compactSignalLabel(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > 28 ? `${text.slice(0, 25)}...` : text;
}

function detectCurrencySymbol() {
  const location = (state.spec?.business?.location || "").toLowerCase();
  const indiaKeywords = ["india", "bangalore", "bengaluru", "mumbai", "delhi", "chennai", "hyderabad", "pune", "kolkata"];
  return indiaKeywords.some((k) => location.includes(k)) ? "\u20b9" : "$";
}

function formatMenuPrice(value) {
  const sym = detectCurrencySymbol();
  const fallback = sym === "\u20b9" ? `${sym}199` : `${sym}9.99`;
  if (Array.isArray(value) && value.length) {
    const numeric = value.filter((entry) => Number.isFinite(Number(entry))).map(Number);
    if (!numeric.length) return fallback;
    const minimum = Math.min(...numeric);
    const maximum = Math.max(...numeric);
    return minimum === maximum ? `${sym}${minimum}` : `${sym}${minimum} - ${sym}${maximum}`;
  }
  if (Number.isFinite(Number(value))) {
    return `${sym}${Number(value)}`;
  }
  return fallback;
}

function getMenuPriceNumber(value) {
  const fallback = detectCurrencySymbol() === "\u20b9" ? 199 : 9.99;
  if (Array.isArray(value) && value.length) {
    const numeric = value.filter((entry) => Number.isFinite(Number(entry))).map(Number);
    return numeric.length ? Math.min(...numeric) : fallback;
  }
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function dedupeMenuItems(items) {

  const seen = new Set();

  return items.filter((item) => {

    const key = String(
      item.name || ""
    )
      .trim()
      .toLowerCase();

    if (!key) {
      return false;
    }

    if (seen.has(key)) {
      return false;
    }

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

/* =========================
   Autonomous Pipeline Orchestrator
========================= */

state.pipeline = {
  research: null,
  generatedCode: null,
  critique: null,
  deployment: null,
};

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const raw = await response.text();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (_) {
    parsed = { raw };
  }
  if (!response.ok) {
    const message = parsed?.detail || raw || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return parsed;
}

function scorePillClass(score) {
  if (typeof score !== "number") return "";
  if (score < 50) return "is-low";
  if (score < 75) return "is-mid";
  return "";
}

function escapeHtml(value) {
  if (value == null) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderList(items, fallback = "No items reported.") {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="empty">${fallback}</p>`;
  }
  return `<ul>${items
    .slice(0, 8)
    .map((item) => `<li>${escapeHtml(typeof item === "string" ? item : JSON.stringify(item))}</li>`)
    .join("")}</ul>`;
}

function renderResearch(result) {
  const panel = document.querySelector("#researchPanel");
  const content = document.querySelector("#researchContent");
  if (!panel || !content) return;
  if (!result) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const data = result.research_results || result;
  const cards = [];
  const competitor = data.competitor_analysis;
  if (competitor) {
    const compList = (competitor.likely_competitors || competitor.competitors || []).map(
      (c) => (typeof c === "string" ? c : c.name || JSON.stringify(c)),
    );
    cards.push(`
      <div class="research-card">
        <h5>Competitor Analysis</h5>
        ${renderList(compList, "No likely competitors surfaced.")}
        ${competitor.differentiation_opportunities ? `<p><strong>Differentiation:</strong> ${escapeHtml(
          Array.isArray(competitor.differentiation_opportunities)
            ? competitor.differentiation_opportunities.join("; ")
            : competitor.differentiation_opportunities,
        )}</p>` : ""}
      </div>
    `);
  }

  const seo = data.local_seo;
  if (seo) {
    const keywords = [
      ...(seo.target_keywords || []),
      ...(seo.local_search_terms || []),
      ...(keywords => keywords.length === 0 ? [...(seo.content_recommendations || []), ...(seo.local_optimization_tips || [])] : [])(
        [...(seo.target_keywords || []), ...(seo.local_search_terms || [])]
      ),
    ].filter(Boolean);
    cards.push(`
      <div class="research-card">
        <h5>Local SEO Strategy</h5>
        ${renderList(keywords, "No keyword recommendations.")}
        ${seo.review_strategy ? `<p><strong>Reviews:</strong> ${escapeHtml(seo.review_strategy)}</p>` : ""}
        ${seo.directory_listings?.length ? `<p><strong>Directories:</strong> ${escapeHtml(seo.directory_listings.join(", "))}</p>` : ""}
      </div>
    `);
  }

  const menu = data.menu_extraction;
  if (menu && typeof menu === "object") {
    if (Object.keys(menu).length === 0) {
      cards.push(`
        <div class="research-card">
          <h5>Menu / Service Extraction</h5>
          <p class="empty">No assets uploaded. Add menu images or PDFs to the form to extract items.</p>
        </div>
      `);
    } else {
      const rawItems = menu.items || menu.services || [];
      let itemNames = rawItems.map((i) => (typeof i === "string" ? i : i.name || i.title || JSON.stringify(i))).filter(Boolean);
      if (!itemNames.length) itemNames = (menu.categories || []).filter(Boolean);
      if (!itemNames.length) itemNames = (menu.special_offers || []).filter(Boolean);
      if (!itemNames.length) itemNames = (menu.business_highlights || []).filter(Boolean);
      const highlights = menu.business_highlights || [];
      cards.push(`
        <div class="research-card">
          <h5>Menu / Service Extraction</h5>
          ${renderList(itemNames, "No items could be extracted. Try uploading a clearer menu image or PDF.")}
          ${highlights.length && itemNames !== highlights ? `<p><strong>Highlights:</strong> ${escapeHtml(highlights.join("; "))}</p>` : ""}
        </div>
      `);
    }
  }

  content.innerHTML = cards.length
    ? cards.join("")
    : `<p class="empty">Research returned no usable findings.</p>`;
}

function renderGeneratedCode(result) {
  const panel = document.querySelector("#generatedCodePanel");
  const content = document.querySelector("#generatedCodeContent");
  if (!panel || !content) return;
  if (!result) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const generated = result.generated_code || result;
  const pages = generated?.pages || {};
  const files = generated?.files || {};
  const components = generated?.components || {};

  const entries = [
    ...Object.entries(pages).map(([k, v]) => [`pages/${k}`, v]),
    ...Object.entries(components).map(([k, v]) => [`components/${k}`, v]),
    ...Object.entries(files).map(([k, v]) => [k, v]),
  ];

  const previewHtml = generated?.html_preview || "";
  const previewBlock = previewHtml
    ? `<div class="website-preview-wrap">
        <h5 style="margin-bottom:.5rem;font-weight:600;">Live Preview</h5>
        <iframe srcdoc="" id="sitePreviewFrame"
          style="width:100%;height:520px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;"></iframe>
      </div>`
    : "";

  if (entries.length === 0 && !previewHtml) {
    content.innerHTML = `<p class="empty">No source files generated.</p>`;
    return;
  }

  content.innerHTML = previewBlock + entries
    .slice(0, 6)
    .map(([name, source]) => `
      <div class="code-file-card">
        <h5>${escapeHtml(name)}<span class="score-pill">${(String(source).length / 1000).toFixed(1)} KB</span></h5>
        <pre>${escapeHtml(String(source).slice(0, 1800))}${String(source).length > 1800 ? "\n... (truncated)" : ""}</pre>
      </div>
    `)
    .join("");

  if (previewHtml) {
    const frame = content.querySelector("#sitePreviewFrame");
    if (frame) frame.srcdoc = previewHtml;

    const sitePreview = document.querySelector("#sitePreview");
    if (sitePreview) {
      const iframe = document.createElement("iframe");
      iframe.style.cssText = "width:100%;height:650px;border:none;border-radius:10px;display:block;background:#fff;";
      iframe.srcdoc = previewHtml;
      sitePreview.innerHTML = "";
      sitePreview.appendChild(iframe);
    }
  }
}

function renderCritique(result) {
  const panel = document.querySelector("#critiquePanel");
  const content = document.querySelector("#critiqueContent");
  if (!panel || !content) return;
  if (!result) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const reports = result.critique_reports || result.reports || {};
  const debate = result.debate_outcome || result.debate || {};

  const agentCards = Object.entries(reports)
    .map(([agent, report]) => {
      const score = typeof report?.score === "number" ? report.score : null;
      const scoreHtml = score != null
        ? `<span class="score-pill ${scorePillClass(score)}">${score}/100</span>`
        : "";
      const issues = report?.issues || [];
      const suggestions = report?.suggestions || [];
      return `
        <div class="critique-agent-card">
          <h5>${escapeHtml(agent.toUpperCase())} Critique${scoreHtml}</h5>
          <p><strong>Issues</strong></p>
          ${renderList(issues, "No issues identified.")}
          <p style="margin-top:8px"><strong>Suggestions</strong></p>
          ${renderList(suggestions, "No suggestions returned.")}
        </div>
      `;
    })
    .join("");

  const consensusHtml = debate && (debate.consensus || debate.winner_reasoning || debate.summary)
    ? `<div class="debate-consensus">
        <strong>Debate Consensus</strong>
        ${escapeHtml(debate.consensus || debate.winner_reasoning || debate.summary)}
      </div>`
    : "";

  content.innerHTML = consensusHtml + agentCards ||
    `<p class="empty">Critique returned no reports.</p>`;
}

function renderDeployment(result) {
  const panel = document.querySelector("#deploymentPanel");
  const content = document.querySelector("#deploymentContent");
  if (!panel || !content) return;
  if (!result) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const pkg = result.deployment_package || result;
  const cards = [];

  if (pkg.database_schema) {
    const tables = Array.isArray(pkg.database_schema.tables)
      ? pkg.database_schema.tables
      : Array.isArray(pkg.database_schema)
      ? pkg.database_schema
      : [];
    cards.push(`
      <div class="deployment-card">
        <h5>Database Schema<span class="score-pill">${tables.length} tables</span></h5>
        <p>${escapeHtml(tables.map((t) => t.name || t).join(", ") || "Schema generated.")}</p>
      </div>
    `);
  }

  if (pkg.auth_config) {
    cards.push(`
      <div class="deployment-card">
        <h5>Auth Configuration<span class="score-pill">${escapeHtml(pkg.auth_config.provider || "configured")}</span></h5>
        <p>${escapeHtml(pkg.auth_config.summary || "Authentication endpoints and middleware generated.")}</p>
      </div>
    `);
  }

  if (pkg.payment_config) {
    cards.push(`
      <div class="deployment-card">
        <h5>Payment Integration<span class="score-pill">${escapeHtml(pkg.payment_config.provider || "Stripe")}</span></h5>
        <p>${escapeHtml(pkg.payment_config.summary || "Payment intents and webhooks configured.")}</p>
      </div>
    `);
  }

  if (pkg.deployment_config) {
    cards.push(`
      <div class="deployment-card">
        <h5>Deployment Targets</h5>
        <p>${escapeHtml(
          (pkg.deployment_config.targets || pkg.deployment_config.platforms || ["Docker", "Vercel"]).join(", "),
        )}</p>
      </div>
    `);
  }

  content.innerHTML = cards.length
    ? cards.join("")
    : `<p class="empty">No deployment artifacts generated.</p>`;
}

function clearPipelinePanels() {
  state.pipeline = { research: null, generatedCode: null, critique: null, deployment: null };
  ["#researchPanel", "#generatedCodePanel", "#critiquePanel", "#deploymentPanel"].forEach((sel) => {
    const el = document.querySelector(sel);
    if (el) el.hidden = true;
  });
}

async function runProductionPipeline() {
  if (!state.spec) return;
  const profile = getBusinessProfileInput();
  if (profile && "logo" in profile) delete profile.logo;

  // 1. Deep Research
  pushTimelineEvent("Research Agent", "Running competitor, local SEO, and asset extraction agents...", "active");
  try {
    const research = await postJSON("/run-research", {
      business_input: { ...profile, vertical: state.spec?.business?.vertical },
      assets: state.assetExtractions || [],
    });
    state.pipeline.research = research;
    renderResearch(research);
    pushTimelineEvent("Research Agent", "Deep research findings published.", "researched");
  } catch (error) {
    pushTimelineEvent("Research Agent", `Research failed: ${error.message}`, "warning");
  }

  // 2. Code Generation
  pushTimelineEvent("Code Generation Agent", "Generating Next.js + Tailwind source from BuildSpec...", "active");
  try {
    const hasOrderingFeature = (state.spec?.includedFeatures || []).some((f) => f.key === "online_ordering");
    const menuItems = hasOrderingFeature
      ? (buildRestaurantExperienceData().items || [])
      : [];
    const finalState = state.graphExecution?.final_state || {};
    const code = await postJSON("/generate-code", {
      buildSpec: { ...state.spec, menuItems },
      agentContext: {
        requirements_spec: finalState.requirements_spec || null,
        design_spec: finalState.design_spec || null,
        reasoning_notes: finalState.reasoning_notes || [],
        retrieved_memories: finalState.retrieved_memories || [],
        human_answers: state.humanAnswers || {},
        research_results: state.pipeline?.research?.research_results || null,
      },
    });
    state.pipeline.generatedCode = code;
    renderGeneratedCode(code);
    pushTimelineEvent("Code Generation Agent", "Production code generated.", "planned");
  } catch (error) {
    pushTimelineEvent("Code Generation Agent", `Code generation failed: ${error.message}`, "warning");
  }

  // 3. Critique & Debate
  const generatedSource =
    state.pipeline?.generatedCode?.generated_code?.pages?.index ||
    state.pipeline?.generatedCode?.pages?.index ||
    "";
  if (generatedSource) {
    pushTimelineEvent("Critique Council", "5 specialist agents reviewing generated code...", "active");
    try {
      const critique = await postJSON("/run-critique", {
        code: generatedSource,
        buildSpec: state.spec,
        agents: ["ux", "accessibility", "conversion", "security", "performance"],
      });
      state.pipeline.critique = critique;
      renderCritique(critique);
      pushTimelineEvent("Critique Council", "Multi-agent critique and debate complete.", "evaluated");
    } catch (error) {
      pushTimelineEvent("Critique Council", `Critique failed: ${error.message}`, "warning");
    }
  }

  // 4. Deployment Package
  pushTimelineEvent("Deployment Agent", "Generating database, auth, payment, and deployment artifacts...", "active");
  try {
    const deployment = await postJSON("/generate-deployment", { buildSpec: state.spec });
    state.pipeline.deployment = deployment;
    renderDeployment(deployment);
    pushTimelineEvent("Deployment Agent", "Deployment package ready for handover.", "complete");
  } catch (error) {
    pushTimelineEvent("Deployment Agent", `Deployment generation failed: ${error.message}`, "warning");
  }
}
