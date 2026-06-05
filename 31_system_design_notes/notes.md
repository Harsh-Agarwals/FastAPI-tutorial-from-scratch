# Notes — Chapter 31

A small list of things experienced engineers know that show up nowhere
in tutorials:

- The first version of any system is mostly *moving JSON around*.
  Make that part dull and reliable.
- Most outages are caused by **change**. Slow rollouts, automatic
  rollbacks, canaries.
- The bug is rarely where you're looking. Add the right logs first,
  then the fix becomes obvious.
- "Eventually consistent" is fine for nearly everything users care about,
  as long as you UI-explain it.
- Your storage tier is *the* hard part to change later. Pick it
  thoughtfully; everything else is replaceable.
- The cheapest performance win is almost always **caching** something
  you didn't realise was being recomputed.
