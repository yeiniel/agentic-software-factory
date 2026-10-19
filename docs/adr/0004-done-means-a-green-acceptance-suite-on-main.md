# A Task is done when the full acceptance suite is green on `main`

The Deliverable is a `main` on which the entire acceptance suite passes, and `main` advances only through the Integrator, only when the suite is green on the integrated result. There is no pull request and no human review in the loop; a Task that cannot get there within its Run cap is Blocked for a human. We chose this over a human-reviewed PR because the point of the experiment is to see how far an automated acceptance gate can carry a Task without a person.
