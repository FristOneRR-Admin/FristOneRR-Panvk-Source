#include <stdio.h>
#include <stddef.h>

struct base_jd_udata {
    unsigned long long blob[2];
};

struct base_jd_atom {
    unsigned long long seq_nr;
    unsigned long long jc;
    struct base_jd_udata udata;
    unsigned long long extres_list;
    unsigned short nr_extres;
    unsigned char jit_id[2];

    struct {
        unsigned char atom_id;
        unsigned char dependency_type;
    } pre_dep[2];

    unsigned char atom_number;
    unsigned char prio;
    unsigned char device_nr;
    unsigned char jobslot;
    unsigned int core_req;
    unsigned char renderpass_id;
    unsigned char padding[7];
};

int main(void)
{
    printf("sizeof(base_jd_atom)=%zu
",
           sizeof(struct base_jd_atom));
    printf("offsetof(seq_nr)=%zu
",
           offsetof(struct base_jd_atom, seq_nr));
    printf("offsetof(jc)=%zu
",
           offsetof(struct base_jd_atom, jc));
    printf("offsetof(atom_number)=%zu
",
           offsetof(struct base_jd_atom, atom_number));
    printf("offsetof(core_req)=%zu
",
           offsetof(struct base_jd_atom, core_req));
    printf("offsetof(padding)=%zu
",
           offsetof(struct base_jd_atom, padding));
    return 0;
}
