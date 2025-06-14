for d in wallypipelinedcore_rv64gc_orig_sky130nm_*; do
  [ -d "$d" ] && ! find "$d" -type f -name "*.rep" | grep -q . && rm -rf "$d"
done