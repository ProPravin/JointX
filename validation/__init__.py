"""
Model validation tooling -- kept separate from ml/ (live inference) and
training/ (fitting a model) because these checks apply to an ALREADY
TRAINED model/dataset and gate whether its numbers may be trusted or
shown at all. See:
  validation/calibration.py -- numeric score honesty gate
  validation/protocols.py   -- honest evaluation for small N, temporal and
                                site/device generalization checks
  validation/subgroups.py   -- fairness audit across demographic/site strata
"""
