#include <qlat/qlat.h>

#include <complex>
#include <iostream>
#include <qlat/vector_utils/general_funs.h>

using namespace qlat;

void simple_tests()
{
  const Coordinate total_site(4, 4, 4, 8);
  Geometry geo;
  geo.init(total_site, 1);

  qlat::RngState rs(1235232);
  {
    double a = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));
    double b = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));

    __float128 a128 = a;
    __float128 b128 = b;
    displayln_info(ssprintf("CHECK: a   %+.8e, b %+.8e \n", a, b));
    const int Ncase = 8;
    qlat::vector_acc<double > ld;ld.resize(4);

    for(int casei = 0; casei < Ncase; casei++)
    {
      const Long V = 16;
      qacc_for(c, V, {
        if(c == 0){
          //ld[0] = a;
          //ld[1] = b;
          Ldouble la = a;
          Ldouble lb = b;
          Ldouble lz = 0.0;

          // add check
          if(casei == 0)
          {
            lz = la + lb;
          }

          // sub check
          if(casei == 1)
          {
            lz = la - lb;
          }

          // * check
          if(casei == 2)
          {
            lz = la * lb;
          }

          // / check
          if(casei == 3)
          {
            lz = la / lb;
          }

          // sqrt check
          if(casei == 4)
          {
            lz = sqrtT(fabsT(la));
          }
          // sin  check
          if(casei == 5)
          {
            lz = qsin(la + lb);
          }
          // cos  check
          if(casei == 6)
          {
            lz = qcos(la + lb);
          }
          // acos check
          if(casei == 7)
          {
            lz = qacos(qsin(la + lb));
          }

          ld[0] = lz.Y();
          ld[1] = lz.X();

          //ld[0] = a;
          //ld[1] = b;
          ////ld[1] = z0;
          ////ld[3] = lz.X();
        }
      });

      __float128 z128;
      std::string ss = "CHECK: ";
      if(casei == 0){ss += "add ";z128 = a128 + b128;}
      if(casei == 1){ss += "sub ";z128 = a128 - b128;}
      if(casei == 2){ss += "mul ";z128 = a128 * b128;}
      if(casei == 3){ss += "div ";z128 = a128 / b128;}
      if(casei == 4){ss += "qrt ";z128 = sqrtq(fabsq(a128));}
      if(casei == 5){ss += "sin ";z128 = qsin(double(a128 + b128));}
      if(casei == 6){ss += "cos ";z128 = qcos(double(a128 + b128));}
      if(casei == 7){ss += "acos";z128 = qacos(qsin(double(a128 + b128)));}
      double rety = (double) z128;
      double retx = (double)(z128-(__float128)rety);
      ld[2] = rety;
      ld[3] = retx;
      qlat::vector_acc<double >& l = ld;
      if(qlat::get_id_node() == 0){
        printf("%+.8e, %+.8e, float128 %+.8e, %+.8e, diff %+.8e, %+.8e \n", l[0], l[1], l[2], l[3], l[0]-l[2], l[1]-l[3]);
      }
      ss += ssprintf("%+.5e, %+.5e, float128 %+.5e, %+.5e \n", l[0], l[1], l[2], l[3]);
      displayln_info(ss);
    }
  }

  {
    double a0 = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));
    double a1 = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));
    double b0 = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));
    double b1 = (1 - 2 * int(qlat::u_rand_gen(rs)*2)) * qlat::u_rand_gen(rs) * (std::pow(10, int(qlat::u_rand_gen(rs)*10)));

    std::complex<__float128 > aC(a0, a1);//(a0, b1);
    std::complex<__float128 > bC(b0, b1);//(a0, b1);
    ComplexT<Ldouble > adC(a0, a1);//(a0, b1);
    ComplexT<Ldouble > bdC(b0, b1);//(a0, b1);

    ComplexT<Ldouble > zdC;
    //std::complex<__float128 > zC;
    //zC  = aC  / bC;
    zdC = adC / bdC;
    zdC = adC * ComplexT<Ldouble>(1.0, 0.0);

    displayln_info(ssprintf("CHECK: a   %+.8e %+.8e, b %+.8e %+.8e \n", a0, a1, b0, b1));
    const int Ncase = 5;
    qlat::vector_acc<double > ld;ld.resize(8);

    for(int casei = 0; casei < Ncase; casei++)
    {
      const Long V = 16;
      qacc_for(c, V, {
        if(c == 0){
          //ld[0] = a;
          //ld[1] = b;
          ComplexT<Ldouble > la(a0, a1);//(a0, b1);
          ComplexT<Ldouble > lb(b0, b1);//(a0, b1);
          ComplexT<Ldouble > lz(0.0, 0.0);

          // add check
          if(casei == 0)
          {
            lz = la + lb;
          }

          // sub check
          if(casei == 1)
          {
            lz = la - lb;
          }

          // * check
          if(casei == 2)
          {
            lz = la * lb;
          }

          // / check
          if(casei == 3)
          {
            lz = la / lb;
          }

          // / check
          if(casei == 4)
          {
            lz = ComplexT<Ldouble>(qlat::qnorm(la), 0.0);
          }

          ld[0] = lz.real().Y();
          ld[1] = lz.real().X();
          ld[2] = lz.imag().Y();
          ld[3] = lz.imag().X();
        }
      });

      std::complex<__float128 > zC;
      std::string ss = "CHECK: ";
      if(casei == 0){ss += "add ";zC = aC + bC;}
      if(casei == 1){ss += "sub ";zC = aC - bC;}
      if(casei == 2){ss += "mul ";zC = aC * bC;}
      if(casei == 3){ss += "div ";zC = aC / bC;}
      if(casei == 4){ss += "nor ";zC = aC.real() * aC.real() + aC.imag() * aC.imag();}
      __float128 zt;
      zt = zC.real();
      double rety = (double) zt;
      double retx = (double)(zt-(__float128)rety);
      ld[4] = rety;
      ld[5] = retx;

      zt = zC.imag();
             rety = (double) zt;
             retx = (double)(zt-(__float128)rety);
      ld[6] = rety;
      ld[7] = retx;
      qlat::vector_acc<double >& l = ld;
      if(qlat::get_id_node() == 0){
        printf("%+.8e, %+.8e, float128 %+.8e, %+.8e, diff %+.8e, %+.8e \n"    , l[0], l[1], l[2], l[3], l[0]-l[4], l[1]-l[5]);
        printf("    %+.8e, %+.8e, float128 %+.8e, %+.8e, diff %+.8e, %+.8e \n", l[4], l[5], l[6], l[7], l[2]-l[6], l[3]-l[7]);
      }
      ss += ssprintf("%+.5e %+.5e, %+.5e %+.5e; "    , l[0], l[1], l[2], l[3]);
      ss += ssprintf("float128 %+.5e %+.5e, %+.5e %+.5e "    , l[4], l[5], l[6], l[7]);
      displayln_info(ss);
    }
  }

  {
    ComplexT<Ldouble > a(1.0, 0.0);
    ComplexT<double  > b(0.6, 0.7);
    ComplexT<double  > c(0.0, 0.0);
    c = b;
    a = b;
    b = a;

    c -= b;
    displayln_info(ssprintf("copy %+.8e %+.8e \n", c.real(), c.real()));

  }

}

int main(int argc, char* argv[])
{
  begin(&argc, &argv);
  get_global_rng_state() = RngState(get_global_rng_state(), "qlat-basic-structure");
  simple_tests();
  displayln_info("CHECK: finished successfully.");
  Timer::display();
  end();
  return 0;
}
